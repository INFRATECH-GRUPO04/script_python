"""Gera telemetria simulada para todos os servidores ativos e envia ao bronze.

Os servidores e seus componentes vêm do MySQL; os CSVs são montados em memória
e gravados diretamente no S3 pela cadeia padrão do boto3: IAM Role na EC2 ou,
opcionalmente, credenciais via .env para testes locais.
"""

import csv
import io
import os
import random
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import boto3
import pymysql
import pymysql.cursors

# Cabeçalhos idênticos aos CABECALHOS do agenteController.js.
CAMPOS_DADOS = [
    "id_empresa", "id_servidor", "username", "data_hora", "cpu", "inte_cpu",
    "ram_disponivel", "ram_total", "ram", "disco", "disco_disponivel", "disco_total",
    "bytes_enviados", "bytes_recebidos", "pacotes_enviados", "pacotes_recebidos",
    "trocas_contexto", "temperatura_cpu", "tempo_escrita_disco",
]
CAMPOS_PROCESSOS = ["id_empresa", "id_servidor", "Usuario", "data_hora", "PID", "Nome", "Username"]

CURVA_HORA = [0.35, 0.28, 0.22, 0.18, 0.15, 0.15, 0.18, 0.25, 0.32, 0.38, 0.42, 0.48,
              0.55, 0.55, 0.55, 0.60, 0.68, 0.75, 0.85, 0.95, 1.00, 0.95, 0.80, 0.55]
PROCESSOS = [(1000 + i, n, "svc_game") for i, n in enumerate(
    ["java", "python", "node", "mysqld", "nginx", "redis-server", "game-server", "cron"])]
LIMITES_PADRAO = {
    "cpu": {"atencao": 80.0, "critico": 95.0},
    "ram": {"atencao": 80.0, "critico": 95.0},
    "disco": {"atencao": 80.0, "critico": 95.0},
}
CONTADORES_INICIAIS = dict(
    interrupcoes=600_000_000,
    bytes_enviados=5_000_000_000,
    bytes_recebidos=3_000_000_000,
    pacotes_enviados=15_000_000,
    pacotes_recebidos=30_000_000,
    trocas_contexto=1_200_000_000,
    temperatura_cpu=58.5,
    tempo_escrita_disco=45_000_000,
)


def carregar_env():
    """Lê o .env local sem dependência extra; na EC2 as variáveis já vêm do ambiente."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(caminho):
        caminho = ".env"
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            if "=" in linha and not linha.lstrip().startswith("#"):
                chave, valor = linha.strip().split("=", 1)
                os.environ.setdefault(chave, valor.strip().strip('"').strip("'"))


def obrigatoria(nome):
    valor = os.getenv(nome)
    if not valor:
        raise RuntimeError(f"Defina {nome} no ambiente ou no arquivo .env.")
    return valor


def inteiro(nome, padrao):
    try:
        return int(os.getenv(nome, str(padrao)))
    except (TypeError, ValueError):
        raise RuntimeError(f"{nome} precisa ser um número inteiro.")


def carregar_fuso(nome):
    """Brasília não tem DST desde 2019; o offset fixo evita depender de tzdata."""
    try:
        return ZoneInfo(nome)
    except Exception:
        return timezone(timedelta(hours=-3))


def carregar_config():
    carregar_env()
    cfg = {
        "db_host": obrigatoria("DB_HOST"),
        "db_database": obrigatoria("DB_DATABASE"),
        "db_user": obrigatoria("DB_USER"),
        "db_password": os.getenv("DB_PASSWORD", ""),
        "db_port": inteiro("DB_PORT", 3306),
        "bucket": obrigatoria("S3_BUCKET"),
        "bronze": os.getenv("S3_BRONZE_PREFIX", "01-bronze/").strip("/") + "/",
        "aws_region": os.getenv("AWS_REGION") or None,
        "fuso": carregar_fuso(os.getenv("FUSO", "America/Sao_Paulo")),
        "dias": max(1, inteiro("DIAS_HISTORICO", 30)),
        "passo": max(1, inteiro("PASSO_SEGUNDOS", 60)),
        "seed": os.getenv("SEED") or "20261125",
        "dias_recentes": max(1, inteiro("DIAS_RECENTES", 7)),
        "lacuna_recente": max(0, inteiro("LACUNA_RECENTE_MINUTOS", 180)),
        "lacuna_antiga_min": max(0, inteiro("LACUNA_ANTIGA_MIN_MINUTOS", 30)),
        "lacuna_antiga_max": max(0, inteiro("LACUNA_ANTIGA_MAX_MINUTOS", 120)),
        "offline_servidores": max(0, inteiro("SERVIDORES_OFFLINE_AGORA", 2)),
        "offline_minutos": max(1, inteiro("OFFLINE_MINUTOS", 50)),
    }
    if cfg["lacuna_antiga_min"] > cfg["lacuna_antiga_max"]:
        raise RuntimeError("LACUNA_ANTIGA_MIN_MINUTOS não pode passar de LACUNA_ANTIGA_MAX_MINUTOS.")
    if cfg["dias_recentes"] > cfg["dias"]:
        cfg["dias_recentes"] = cfg["dias"]
    return cfg


def conectar(cfg):
    return pymysql.connect(
        host=cfg["db_host"],
        port=cfg["db_port"],
        user=cfg["db_user"],
        password=cfg["db_password"],
        database=cfg["db_database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
    )


def carregar_servidores(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """SELECT s.id_servidor, s.fk_empresa AS id_empresa, s.nome
               FROM servidor s
               WHERE s.status_sistema = 1
               ORDER BY s.id_servidor"""
        )
        return cursor.fetchall()


def carregar_componentes(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """SELECT c.fk_servidor AS id_servidor, c.tipo, c.capacidade_total,
                      m.limite_atencao, m.limite_critico
               FROM componente c
               JOIN servidor s ON s.id_servidor = c.fk_servidor
               LEFT JOIN metrica m ON m.fk_componente = c.id_componente
                                  AND m.nome = 'uso_percentual'
               WHERE s.status_sistema = 1 AND c.status_monitoramento = 1
               ORDER BY c.fk_servidor, c.tipo"""
        )
        linhas = cursor.fetchall()
    por_servidor = defaultdict(dict)
    for linha in linhas:
        por_servidor[int(linha["id_servidor"])][str(linha["tipo"]).lower()] = linha
    return por_servidor


def numero_ou_none(valor):
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def construir_perfil(servidor, componentes):
    """Perfil do servidor com capacidades e limites reais do banco."""
    id_servidor = int(servidor["id_servidor"])
    componentes_servidor = componentes.get(id_servidor, {})
    tamanho = id_servidor % 3

    perfil = dict(CONTADORES_INICIAIS)
    perfil.update(
        id_empresa=int(servidor["id_empresa"]),
        id_servidor=id_servidor,
        nome=servidor["nome"] or f"Servidor-{id_servidor}",
        ram_total=[8, 16, 32][tamanho],
        disco_total=[256, 512, 1000][tamanho],
        capacidade_rede_mbps=1000.0,
        capacidade_jogadores=60,
        fator=0.7 + (id_servidor % 4) * 0.1,
        ram_base=25 + id_servidor % 10,
        tem_vazamento=id_servidor % 4 == 0,
        vazamento=0.0,
        limites={},
        ultima_captura=None,
    )

    ram = numero_ou_none((componentes_servidor.get("ram") or {}).get("capacidade_total"))
    disco = numero_ou_none((componentes_servidor.get("disco") or {}).get("capacidade_total"))
    rede = numero_ou_none((componentes_servidor.get("rede") or {}).get("capacidade_total"))
    if ram and ram > 0:
        perfil["ram_total"] = ram
    if disco and disco > 0:
        perfil["disco_total"] = disco
    if rede and rede > 0:
        perfil["capacidade_rede_mbps"] = rede
    perfil["capacidade_jogadores"] = max(30, int(perfil["capacidade_rede_mbps"] * 0.03))

    for tipo in ("cpu", "ram", "disco"):
        componente = componentes_servidor.get(tipo) or {}
        atencao = numero_ou_none(componente.get("limite_atencao"))
        critico = numero_ou_none(componente.get("limite_critico"))
        padrao = LIMITES_PADRAO[tipo]
        if atencao is None or atencao <= 0 or atencao >= 100:
            atencao = padrao["atencao"]
        if critico is None or critico <= atencao or critico > 100:
            critico = padrao["critico"]
        perfil["limites"][tipo] = {"atencao": atencao, "critico": critico}
    return perfil


def escolher_destaques(servidores, cfg):
    """Separa quem fica offline agora e quem exibe atenção/crítico na última leitura."""
    ids = sorted(int(servidor["id_servidor"]) for servidor in servidores)
    rng = random.Random(f"{cfg['seed']}|offline")
    rng.shuffle(ids)
    offline = set(ids[: cfg["offline_servidores"]])

    online = [id_servidor for id_servidor in ids if id_servidor not in offline]
    rng = random.Random(f"{cfg['seed']}|destaques")
    rng.shuffle(online)
    destaques = {}
    if online:
        destaques[online[0]] = {"recurso": "cpu", "nivel": "critico"}
    if len(online) > 1:
        destaques[online[1]] = {"recurso": "ram", "nivel": "atencao"}
    return offline, destaques


def agendar_ausencias(perfil, momentos, cfg, offline_ids):
    """Lacunas por dia: 3h na última semana, 30–120min antes dela."""
    rng = random.Random(f"{cfg['seed']}|{perfil['id_empresa']}|{perfil['id_servidor']}|lacunas")
    ausencias = set()
    por_dia = defaultdict(list)
    for indice, momento in enumerate(momentos):
        por_dia[momento.date()].append(indice)

    hoje = momentos[-1].date()
    inicio_recente = hoje - timedelta(days=cfg["dias_recentes"] - 1)
    for dia, indices in por_dia.items():
        duracao = cfg["lacuna_recente"] if dia >= inicio_recente else rng.randint(
            cfg["lacuna_antiga_min"], cfg["lacuna_antiga_max"]
        )
        passos = duracao * 60 // cfg["passo"]
        if passos <= 0:
            continue
        max_inicio = max(0, len(indices) - passos)
        inicio = rng.randint(0, max_inicio) if max_inicio else 0
        ausencias.update(indices[inicio : inicio + passos])

    total = len(momentos)
    if perfil["id_servidor"] in offline_ids:
        passos_offline = cfg["offline_minutos"] * 60 // cfg["passo"]
        ultimo = max(0, total - 1 - passos_offline)
        ausencias.discard(ultimo)
        ausencias.update(range(ultimo + 1, total))
    else:
        ausencias.discard(total - 1)  # servidor online termina exatamente em "agora"
    return ausencias


def possivel_pico(valor, faixa, rng):
    """Picos esporádicos calibrados pelos limites cadastrados no banco."""
    if rng.random() < 0.003:
        if rng.random() < 0.35:
            alvo = faixa["critico"] + rng.uniform(0.5, 3)
        else:
            alvo = faixa["atencao"] + rng.uniform(0.5, 3)
        valor = max(valor, alvo)
    return round(min(100.0, max(0.0, valor)), 1)


def valor_em_destaque(perfil, nivel):
    faixa = perfil["limites"]["cpu" if nivel == "critico" else "ram"]
    if nivel == "critico":
        alvo = faixa["critico"] + 2
    else:
        alvo = min(faixa["atencao"] + 2, faixa["critico"] - 1)
    return round(min(100.0, max(0.0, alvo)), 1)


def gerar_linha(perfil, momento, delta_segundos, rng, destaque):
    carga = CURVA_HORA[momento.hour] * perfil["fator"] * rng.uniform(0.9, 1.1)
    if momento.weekday() >= 5:
        carga *= 1.15
    jogadores = int(carga * perfil["capacidade_jogadores"])

    cpu = 5 + 75 * carga + rng.uniform(-3, 3)
    if rng.random() < 0.03:
        cpu += rng.uniform(10, 20)
    cpu = possivel_pico(cpu, perfil["limites"]["cpu"], rng)
    if destaque and destaque["recurso"] == "cpu":
        cpu = valor_em_destaque(perfil, destaque["nivel"])

    if perfil["tem_vazamento"]:
        perfil["vazamento"] += 0.015 * (delta_segundos / 60)
    ram = perfil["ram_base"] + 20 * carga + perfil["vazamento"] + rng.uniform(-0.5, 0.5)
    if ram >= 92:
        perfil["vazamento"] = 0.0
        ram = perfil["ram_base"] + 20 * carga
    ram = possivel_pico(ram, perfil["limites"]["ram"], rng)
    if destaque and destaque["recurso"] == "ram":
        ram = valor_em_destaque(perfil, destaque["nivel"])

    dias = (momento - datetime(2026, 1, 1, tzinfo=momento.tzinfo)).days
    disco = round(min(100, 40 + perfil["id_servidor"] % 10 + (dias % 30) * 1.2), 1)
    disco = possivel_pico(disco, perfil["limites"]["disco"], rng)

    capacidade = perfil["capacidade_rede_mbps"]
    alvo_mbps = capacidade * (0.12 + 0.55 * carga) * rng.uniform(0.85, 1.15)
    alvo_mbps = max(0.5, min(capacidade * 0.95, alvo_mbps))
    perfil["bytes_enviados"] += int(alvo_mbps * 1_000_000 / 8 * delta_segundos)
    perfil["bytes_recebidos"] += int(alvo_mbps * 0.35 * 1_000_000 / 8 * delta_segundos)
    perfil["pacotes_enviados"] = perfil["bytes_enviados"] // 300
    perfil["pacotes_recebidos"] = perfil["bytes_recebidos"] // 100
    perfil["interrupcoes"] += int((8000 + 250 * cpu) * delta_segundos)
    perfil["trocas_contexto"] += int(
        (15000 + 400 * cpu + jogadores * 50) * delta_segundos * rng.uniform(0.95, 1.05)
    )
    perfil["temperatura_cpu"] = round(min(100.0, 40.0 + cpu * 0.45 + rng.uniform(-1.5, 1.5)), 1)
    perfil["tempo_escrita_disco"] += int(
        (5 + jogadores * 1.5) * delta_segundos * rng.uniform(0.8, 1.3)
    )

    return {
        "id_empresa": perfil["id_empresa"],
        "id_servidor": perfil["id_servidor"],
        "username": perfil["nome"],
        "data_hora": momento.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": cpu,
        "inte_cpu": perfil["interrupcoes"],
        "ram_disponivel": round(perfil["ram_total"] * (1 - ram / 100), 3),
        "ram_total": perfil["ram_total"],
        "ram": ram,
        "disco": disco,
        "disco_disponivel": round(perfil["disco_total"] * (1 - disco / 100), 3),
        "disco_total": perfil["disco_total"],
        "bytes_enviados": perfil["bytes_enviados"],
        "bytes_recebidos": perfil["bytes_recebidos"],
        "pacotes_enviados": perfil["pacotes_enviados"],
        "pacotes_recebidos": perfil["pacotes_recebidos"],
        "trocas_contexto": perfil["trocas_contexto"],
        "temperatura_cpu": perfil["temperatura_cpu"],
        "tempo_escrita_disco": perfil["tempo_escrita_disco"],
    }


def gerar_serie(perfil, momentos, ausencias, cfg, destaque):
    rng = random.Random(f"{cfg['seed']}|{perfil['id_empresa']}|{perfil['id_servidor']}|valores")
    linhas = []
    for indice, momento in enumerate(momentos):
        if indice in ausencias:
            continue
        delta = cfg["passo"] if perfil["ultima_captura"] is None else (
            momento - perfil["ultima_captura"]
        ).total_seconds()
        atual = destaque if indice == len(momentos) - 1 else None
        linhas.append(gerar_linha(perfil, momento, delta, rng, atual))
        perfil["ultima_captura"] = momento
    return linhas


def csv_para_bytes(campos, linhas):
    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=campos, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(linhas)
    return saida.getvalue().encode("utf-8")


def cliente_s3(cfg):
    return boto3.client("s3", region_name=cfg["aws_region"]) if cfg["aws_region"] else boto3.client("s3")


def media(numeros):
    return round(sum(numeros) / len(numeros), 1) if numeros else None


def estimar_disponibilidade(ausencias_por_servidor, momentos, cfg):
    """Espelho simplificado do cálculo do gold, só para conferir no log."""
    por_dia = defaultdict(lambda: defaultdict(
        lambda: {"recebidas": 0, "primeiro": None, "ultimo": None}
    ))
    for id_servidor, ausencias in ausencias_por_servidor.items():
        for indice, momento in enumerate(momentos):
            if indice in ausencias:
                continue
            item = por_dia[momento.date()][id_servidor]
            item["recebidas"] += 1
            if item["primeiro"] is None:
                item["primeiro"] = momento
            item["ultimo"] = momento

    hoje = momentos[-1].date()
    inicio_recente = hoje - timedelta(days=cfg["dias_recentes"] - 1)
    valores = []
    for dia in sorted(por_dia):
        total_recebidas = total_esperadas = 0.0
        for item in por_dia[dia].values():
            recebidas = item["recebidas"]
            fim = item["ultimo"] + timedelta(seconds=cfg["passo"])
            if dia == hoje:
                # O gold usa fim exclusivo em "agora": a captura final não entra.
                if item["ultimo"] == momentos[-1]:
                    recebidas -= 1
                fim = min(fim, momentos[-1])
            esperadas = (fim - item["primeiro"]).total_seconds() / cfg["passo"]
            if esperadas > 0:
                total_recebidas += recebidas
                total_esperadas += esperadas
        if total_esperadas > 0:
            valores.append((dia, min(100.0, total_recebidas / total_esperadas * 100)))
    recentes = [valor for dia, valor in valores if dia >= inicio_recente]
    return media(recentes), media([valor for _, valor in valores])


def main():
    cfg = carregar_config()
    conexao = conectar(cfg)
    try:
        servidores = carregar_servidores(conexao)
        componentes = carregar_componentes(conexao)
    finally:
        conexao.close()
    if not servidores:
        raise RuntimeError("Nenhum servidor ativo encontrado no banco.")

    offline_ids, destaques = escolher_destaques(servidores, cfg)
    agora = datetime.now(cfg["fuso"])
    total = int(cfg["dias"] * 86400 // cfg["passo"]) + 1
    inicio = agora - timedelta(seconds=(total - 1) * cfg["passo"])
    momentos = [inicio + timedelta(seconds=i * cfg["passo"]) for i in range(total)]
    lote = agora.strftime("%Y%m%dT000000Z")
    cliente = cliente_s3(cfg)
    ausencias_por_servidor = {}

    for servidor in servidores:
        perfil = construir_perfil(servidor, componentes)
        ausencias = agendar_ausencias(perfil, momentos, cfg, offline_ids)
        linhas = gerar_serie(perfil, momentos, ausencias, cfg, destaques.get(perfil["id_servidor"]))
        ausencias_por_servidor[perfil["id_servidor"]] = ausencias
        prefixo = (
            f"{lote}_empresa-{perfil['id_empresa']}_servidor-{perfil['id_servidor']}"
        )
        cliente.put_object(
            Bucket=cfg["bucket"],
            Key=f"{cfg['bronze']}{prefixo}_dados.csv",
            Body=csv_para_bytes(CAMPOS_DADOS, linhas),
            ContentType="text/csv",
        )

        hora_final = linhas[-1]["data_hora"] if linhas else momentos[-1].strftime("%Y-%m-%d %H:%M:%S")
        processos = [
            dict(zip(CAMPOS_PROCESSOS, [
                perfil["id_empresa"], perfil["id_servidor"], perfil["nome"], hora_final,
                pid, nome_processo, usuario,
            ]))
            for pid, nome_processo, usuario in PROCESSOS
        ]
        cliente.put_object(
            Bucket=cfg["bucket"],
            Key=f"{cfg['bronze']}{prefixo}_processos.csv",
            Body=csv_para_bytes(CAMPOS_PROCESSOS, processos),
            ContentType="text/csv",
        )

        situacao = "offline" if perfil["id_servidor"] in offline_ids else "online"
        print(
            f"{prefixo}: {len(linhas)} capturas | final {hora_final} | {situacao} | "
            f"{len(ausencias)} minutos sem captura"
        )

    recente, total_geral = estimar_disponibilidade(ausencias_por_servidor, momentos, cfg)
    print(
        f"Concluído: {len(servidores)} servidores, chave do lote {lote}. "
        f"Estimativa gold -> 7d: {recente if recente is not None else '—'}% | "
        f"30d: {total_geral if total_geral is not None else '—'}%"
    )


if __name__ == "__main__":
    main()
