import csv  # Para gerar os arquivos csv
import os  # Para apagar o arquivo depois que ele for enviado
import random  # Para variar os dados da simulação
import time  # Para esperar entre uma captura e outra
import psutil  # Para capturar os dados da máquina e os processos
import requests  # Para falar com o back-end (pip install requests)
from datetime import datetime, timedelta, timezone  # Data e hora

# ---------------- CONFIGURAÇÕES ----------------
URL_API = "http://107.23.216.27"  # Endereço do back-end
MODO_SIMULACAO = True  # True = simula um servidor de jogo | False = lê a máquina de verdade
INTERVALO = 60  # Segundos entre uma captura e outra (1 minuto)
CAPTURAS_POR_LOTE = 10  # 10 capturas de 1 minuto = envio a cada 10 minutos

print("""
==========================================================================================
    ######  ###    ##  ######  ######     ####      ########  #######    ####  ##   ##
      ##    ## #   ##  ##      ##    #  ##    ##       ##     ##       ##      ##   ##
      ##    ##  #  ##  ####    ######   ##    ##       ##     #####    ##      #######
      ##    ##   # ##  ##      ##  ##   ########       ##     ##       ##      ##   ##
    ######  ##    ###  ##      ##    #  ##    ##       ##     #######    ####  ##   ##
==========================================================================================
""")

# ---------------- AUTENTICAÇÃO: pede a chave e o back-end diz de qual empresa e servidor ela é ----------------
while True:
    chave = input("Digite a chave do servidor: ").strip()
    try:
        resposta = requests.post(URL_API + "/agente/autenticar", headers={"x-chave-servidor": chave}, timeout=15)
    except Exception:
        print("Não consegui falar com o back-end. Confira o endereço e a internet.")
        continue
    if resposta.status_code == 200:
        dados_chave = resposta.json()  # Ex.: {"idEmpresa": 1, "idServidor": 3, "nomeServidor": "SRV-BR-01"}
        id_empresa = dados_chave["idEmpresa"]
        id_servidor = dados_chave["idServidor"]
        nome_servidor = dados_chave["nomeServidor"]
        break
    print("Chave inválida. Tente de novo.")
print(f"Servidor autenticado: empresa {id_empresa}, servidor {id_servidor}.")

# ---------------- PERFIL DA MÁQUINA SIMULADA (depende do id, então cada servidor é diferente) ----------------
tamanho = id_servidor % 3
ram_total = [8, 16, 32][tamanho]  # GB de RAM: pequeno, médio ou grande
disco_total = [256, 512, 1000][tamanho]  # GB de disco
capacidade = [60, 150, 300][tamanho]  # Máximo de jogadores
fator = 0.7 + (id_servidor % 4) * 0.1  # De 0.7 a 1.0: quão cheio o servidor fica no pico
ram_base = 25 + id_servidor % 10  # % de RAM usada com o servidor vazio
tem_vazamento = id_servidor % 4 == 0  # Alguns servidores têm vazamento de memória
vazamento = 0  # Quanto de RAM o vazamento já ocupou (em %)

# Quantos jogadores existem em cada hora do dia (0h a 23h): vale de madrugada e pico à noite
curva_hora = [0.35, 0.28, 0.22, 0.18, 0.15, 0.15, 0.18, 0.25, 0.32, 0.38, 0.42, 0.48,
              0.55, 0.55, 0.55, 0.60, 0.68, 0.75, 0.85, 0.95, 1.00, 0.95, 0.80, 0.55]

# Contadores que só aumentam (como os de verdade)
interrupcoes = 600000000
bytes_enviados = 5000000000
bytes_recebidos = 3000000000
pacotes_enviados = 15000000
pacotes_recebidos = 30000000

campos_dados = ['id_empresa', 'id_servidor', 'username', 'data_hora', 'cpu', 'inte_cpu', 'ram_disponivel', 'ram_total',
                'ram', 'disco', 'disco_disponivel', 'disco_total', 'bytes_enviados', 'bytes_recebidos',
                'pacotes_enviados', 'pacotes_recebidos']
campos_processos = ['id_empresa', 'id_servidor', 'Usuario', 'data_hora', 'PID', 'Nome', 'Username']

print(f"Capturando a cada {INTERVALO}s e enviando a cada {INTERVALO * CAPTURAS_POR_LOTE}s. Ctrl+C para parar.\n")

while True:  # Cada volta do while é um lote
    linhas = []
    lote = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # Nome do lote: quando ele começou

    for captura in range(CAPTURAS_POR_LOTE):  # Cada volta do for é uma captura (1 minuto)
        agora = datetime.now(timezone.utc)  # Tudo em UTC

        if MODO_SIMULACAO:
            hora_local = agora - timedelta(hours=3)  # Horário de Brasília: é quando os jogadores jogam
            carga = curva_hora[hora_local.hour] * fator * random.uniform(0.9, 1.1)
            if hora_local.weekday() >= 5:  # Sábado e domingo têm mais jogadores
                carga = carga * 1.15
            jogadores = int(carga * capacidade)

            # CPU: nível ocioso + parte que depende dos jogadores. min/max garantem de 0 a 100.
            cpu = 5 + 75 * carga + random.uniform(-3, 3)
            if random.random() < 0.03:  # Às vezes tem um pico curto
                cpu = cpu + random.uniform(10, 20)
            cpu = round(max(0.5, min(100, cpu)), 1)

            # RAM: base + parte que depende dos jogadores + vazamento (se tiver)
            if tem_vazamento:
                vazamento = vazamento + 0.015
            ram = ram_base + 20 * carga + vazamento + random.uniform(-0.5, 0.5)
            if ram >= 92:  # Faltou memória: o jogo reinicia e o vazamento zera
                vazamento = 0
                ram = ram_base + 20 * carga
            ram = round(max(0, min(100, ram)), 1)
            ram_disponivel = round(ram_total * (1 - ram / 100), 3)

            # Disco: sobe devagar e volta quando limpam os logs (a cada 30 dias)
            dias = (agora - datetime(2026, 1, 1, tzinfo=timezone.utc)).days
            disco = round(min(100, 40 + id_servidor % 10 + (dias % 30) * 1.2), 1)
            disco_disponivel = round(disco_total * (1 - disco / 100), 3)

            # Rede: proporcional ao número de jogadores
            interrupcoes = interrupcoes + int((8000 + 250 * cpu) * INTERVALO)
            bytes_enviados = bytes_enviados + int(jogadores * 5000 * INTERVALO * random.uniform(0.9, 1.1))
            bytes_recebidos = bytes_recebidos + int(jogadores * 1500 * INTERVALO * random.uniform(0.9, 1.1))
            pacotes_enviados = bytes_enviados // 300
            pacotes_recebidos = bytes_recebidos // 100
            print(f"   jogadores simulados: {jogadores}")

        else:  # Leitura da máquina de verdade
            cpu = psutil.cpu_percent(interval=1)
            interrupcoes = psutil.cpu_stats().interrupts
            ram = psutil.virtual_memory().percent
            ram_total = round(psutil.virtual_memory().total / 1024 ** 3, 3)
            ram_disponivel = round(psutil.virtual_memory().available / 1024 ** 3, 3)
            disco = psutil.disk_usage('/').percent
            disco_total = round(psutil.disk_usage('/').total / 1024 ** 3, 3)
            disco_disponivel = round(psutil.disk_usage('/').free / 1024 ** 3, 3)
            bytes_enviados = psutil.net_io_counters().bytes_sent
            bytes_recebidos = psutil.net_io_counters().bytes_recv
            pacotes_enviados = psutil.net_io_counters().packets_sent
            pacotes_recebidos = psutil.net_io_counters().packets_recv

        hora = agora.strftime("%Y-%m-%d %H:%M:%S")
        linhas.append({'id_empresa': id_empresa, 'id_servidor': id_servidor, 'username': nome_servidor,
                       'data_hora': hora, 'cpu': cpu, 'inte_cpu': interrupcoes, 'ram_disponivel': ram_disponivel,
                       'ram_total': ram_total, 'ram': ram, 'disco': disco, 'disco_disponivel': disco_disponivel,
                       'disco_total': disco_total, 'bytes_enviados': bytes_enviados,
                       'bytes_recebidos': bytes_recebidos, 'pacotes_enviados': pacotes_enviados,
                       'pacotes_recebidos': pacotes_recebidos})
        print(f"[{hora} UTC] CPU: {cpu}% | RAM: {ram}% | Disco: {disco}%")
        time.sleep(INTERVALO)

    # ---------------- FIM DO LOTE: gera os CSVs ----------------
    arquivo_dados = f"dados_{lote}.csv"
    with open(arquivo_dados, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=campos_dados)
        writer.writeheader()
        writer.writerows(linhas)

    arquivo_processos = f"processos_{lote}.csv"  # Um retrato dos processos por lote
    with open(arquivo_processos, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=campos_processos)
        writer.writeheader()
        for processo in psutil.process_iter(['pid', 'name', 'username']):
            info = processo.info
            if info['username'] is not None:
                writer.writerow({'id_empresa': id_empresa, 'id_servidor': id_servidor, 'Usuario': nome_servidor,
                                 'data_hora': hora, 'PID': info['pid'], 'Nome': info['name'],
                                 'Username': info['username']})

    # ---------------- ENVIA OS CSVs PARA O BACK-END (ele grava no S3) ----------------
    # Envia todos os dados_*.csv e processos_*.csv da pasta: o que falhou antes é reenviado agora
    for arquivo in sorted(os.listdir('.')):
        if arquivo.startswith("dados_") or arquivo.startswith("processos_"):
            tipo = arquivo.split("_")[0]  # "dados" ou "processos"
            lote_do_arquivo = arquivo.split("_")[1][:-4]  # Tira o ".csv"
            try:
                with open(arquivo, 'rb') as csvfile:
                    resposta = requests.post(URL_API + "/agente/enviar", data=csvfile.read(), timeout=30,
                                             headers={"x-chave-servidor": chave, "x-tipo-arquivo": tipo,
                                                      "x-lote-inicio": lote_do_arquivo, "Content-Type": "text/csv"})
                if resposta.status_code == 200:
                    os.remove(arquivo)  # Enviou, então pode apagar
                    print(f"Enviado: {arquivo}")
                else:
                    print(f"O back-end recusou {arquivo} (código {resposta.status_code}). Arquivo mantido.")
            except Exception:
                print(f"Sem conexão com o back-end. {arquivo} fica salvo e será enviado no próximo lote.")
