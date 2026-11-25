import csv
import os
import random
from datetime import datetime, timedelta, timezone

# Alvo: todos os servidores do INSERT atual (IDs gerados por AUTO_INCREMENT).
SERVIDORES = {1: [1, 2], 2: [3, 4, 5], 3: [6, 7], 4: [8, 9]}
NOMES = {1: "SRV-INFRA-01", 2: "SRV-INFRA-02", 3: "SRV-GAMECLOUD-01", 4: "SRV-GAMECLOUD-02",
         5: "SRV-GAMECLOUD-LEGADO", 6: "SRV-TECHPLAY-01", 7: "SRV-TECHPLAY-02",
         8: "SRV-ARENA-01", 9: "Servidor-B21X7M"}
DIAS = 30
PASSO = 60  # segundos entre leituras (o gold exige <= 30s para calcular rede)
FUSO = timezone(timedelta(hours=-3))  # BRT, sem sufixo na data_hora (igual ao agente)
INICIO_2026 = datetime(2026, 1, 1, tzinfo=FUSO)
PASTA = "dados_simulados"

# Cabeçalhos idênticos aos CABECALHOS do agenteController.js.
CAMPOS_DADOS = ["id_empresa", "id_servidor", "username", "data_hora", "cpu", "inte_cpu",
                "ram_disponivel", "ram_total", "ram", "disco", "disco_disponivel", "disco_total",
                "bytes_enviados", "bytes_recebidos", "pacotes_enviados", "pacotes_recebidos",
                "trocas_contexto", "temperatura_cpu", "tempo_escrita_disco"]
CAMPOS_PROCESSOS = ["id_empresa", "id_servidor", "Usuario", "data_hora", "PID", "Nome", "Username"]

CURVA_HORA = [0.35, 0.28, 0.22, 0.18, 0.15, 0.15, 0.18, 0.25, 0.32, 0.38, 0.42, 0.48,
              0.55, 0.55, 0.55, 0.60, 0.68, 0.75, 0.85, 0.95, 1.00, 0.95, 0.80, 0.55]
PROCESSOS = [(1000 + i, n, "svc_game") for i, n in enumerate(
    ["java", "python", "node", "mysqld", "nginx", "redis-server", "game-server", "cron"])]


def perfil(id_servidor):
    """Perfil do servidor simulado e contadores que só crescem."""
    tamanho = id_servidor % 3
    return dict(ram_total=[8, 16, 32][tamanho], disco_total=[256, 512, 1000][tamanho],
                capacidade=[60, 150, 300][tamanho], fator=0.7 + (id_servidor % 4) * 0.1,
                ram_base=25 + id_servidor % 10, tem_vazamento=id_servidor % 4 == 0, vazamento=0,
                interrupcoes=600_000_000, bytes_enviados=5_000_000_000, bytes_recebidos=3_000_000_000,
                pacotes_enviados=15_000_000, pacotes_recebidos=30_000_000,
                trocas_contexto=1_200_000_000, temperatura_cpu=58.5, tempo_escrita_disco=45_000_000)


def gerar_linha(agora, empresa, servidor, nome, e):
    """Simula um minuto usando as mesmas fórmulas de captura_servidor.py."""
    carga = CURVA_HORA[agora.hour] * e["fator"] * random.uniform(0.9, 1.1)
    if agora.weekday() >= 5:  # fim de semana tem mais jogadores
        carga *= 1.15
    jogadores = int(carga * e["capacidade"])

    cpu = 5 + 75 * carga + random.uniform(-3, 3)
    if random.random() < 0.03:  # pico curto
        cpu += random.uniform(10, 20)
    cpu = round(max(0.5, min(100, cpu)), 1)

    if e["tem_vazamento"]:
        e["vazamento"] += 0.015
    ram = e["ram_base"] + 20 * carga + e["vazamento"] + random.uniform(-0.5, 0.5)
    if ram >= 92:  # falta de memória: o jogo reinicia e zera o vazamento
        e["vazamento"] = 0
        ram = e["ram_base"] + 20 * carga
    ram = round(max(0, min(100, ram)), 1)

    dias = (agora - INICIO_2026).days
    disco = round(min(100, 40 + servidor % 10 + (dias % 30) * 1.2), 1)

    e["interrupcoes"] += int((8000 + 250 * cpu) * PASSO)
    e["bytes_enviados"] += int(jogadores * 5000 * PASSO * random.uniform(0.9, 1.1))
    e["bytes_recebidos"] += int(jogadores * 1500 * PASSO * random.uniform(0.9, 1.1))
    e["pacotes_enviados"] = e["bytes_enviados"] // 300
    e["pacotes_recebidos"] = e["bytes_recebidos"] // 100
    e["trocas_contexto"] += int((15000 + 400 * cpu + jogadores * 50) * PASSO * random.uniform(0.95, 1.05))
    e["temperatura_cpu"] = round(40.0 + cpu * 0.45 + random.uniform(-1.5, 1.5), 1)
    e["tempo_escrita_disco"] += int((5 + jogadores * 1.5) * PASSO * random.uniform(0.8, 1.3))

    return {"id_empresa": empresa, "id_servidor": servidor, "username": nome,
            "data_hora": agora.strftime("%Y-%m-%d %H:%M:%S"), "cpu": cpu,
            "inte_cpu": e["interrupcoes"],
            "ram_disponivel": round(e["ram_total"] * (1 - ram / 100), 3),
            "ram_total": e["ram_total"], "ram": ram, "disco": disco,
            "disco_disponivel": round(e["disco_total"] * (1 - disco / 100), 3),
            "disco_total": e["disco_total"], "bytes_enviados": e["bytes_enviados"],
            "bytes_recebidos": e["bytes_recebidos"], "pacotes_enviados": e["pacotes_enviados"],
            "pacotes_recebidos": e["pacotes_recebidos"], "trocas_contexto": e["trocas_contexto"],
            "temperatura_cpu": e["temperatura_cpu"], "tempo_escrita_disco": e["tempo_escrita_disco"]}


def escrever_csv(caminho, campos, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)


def main():
    os.makedirs(PASTA, exist_ok=True)
    fim = datetime.now(FUSO).replace(second=0, microsecond=0)
    inicio = fim - timedelta(days=DIAS)
    lote = inicio.strftime("%Y%m%dT%H%M%SZ")  # nome aceito pelo bronze2silver.py
    total = DIAS * 24 * 60

    for empresa, servidores in SERVIDORES.items():
        for servidor in servidores:
            nome = NOMES[servidor]
            estado = perfil(servidor)
            linhas = [gerar_linha(inicio + timedelta(minutes=i), empresa, servidor, nome, estado)
                      for i in range(total)]
            prefixo = f"{lote}_empresa-{empresa}_servidor-{servidor}"
            escrever_csv(os.path.join(PASTA, prefixo + "_dados.csv"), CAMPOS_DADOS, linhas)

            hora_final = linhas[-1]["data_hora"]
            processos = [dict(zip(CAMPOS_PROCESSOS, [empresa, servidor, nome, hora_final, pid, proc, user]))
                         for pid, proc, user in PROCESSOS]
            escrever_csv(os.path.join(PASTA, prefixo + "_processos.csv"), CAMPOS_PROCESSOS, processos)
            print(f"{prefixo}: {len(linhas)} linhas")


if __name__ == "__main__":
    main()
