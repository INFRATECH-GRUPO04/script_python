import csv #para gerar o arquivo csv
import psutil #para capturar os dados dos componentes
from datetime import datetime #data e hora

CONFIG = { #configuração do nome do usuario, linha escrita e qtd de linhas
    "username": "Servidor-B21X7M",
    "write_interval": 1,
    "csv_lines": 10
}

print(f"""
==========================================================================================
    ######  ###    ##  ######  ######     ####      ########  #######    ####  ##   ##
      ##    ## #   ##  ##      ##    #  ##    ##       ##     ##       ##      ##   ##
      ##    ##  #  ##  ####    ######   ##    ##       ##     #####    ##      #######
      ##    ##   # ##  ##      ##  ##   ########       ##     ##       ##      ##   ##
    ######  ##    ###  ##      ##    #  ##    ##       ##     #######    ####  ##   ##
==========================================================================================
""")
print("\n"* 2)

def capturar_dados(): # Função que captura os dados
    print("Iniciando a Captura dos Dados: ")
    dados_linhas_csv = CONFIG["csv_lines"]
    processos_linhas_csv = CONFIG["csv_lines"]

    with open(f'./dados_{CONFIG["username"]}.csv', 'w', newline='') as csvfile:
        fieldNames = ['username', 'data_hora' ,'cpu', 'inte_cpu' ,'ram_disponivel', 'ram_total', 'ram' ,'disco', 'disco_disponivel', 'disco_total']
        writer = csv.DictWriter(csvfile, fieldnames=fieldNames)
        writer.writeheader()

        while(dados_linhas_csv > 0): #loop para criar cada linha

            #CPU:
            cpu_percent = psutil.cpu_percent(interval=CONFIG["write_interval"]) #uso da cpu no intervalo configurado, em %
            cpu_interruption = psutil.cpu_stats().interrupts #contagem de interrupções em decimal

            #RAM:
            conversor = 1024 ** 3
            
            mem_percent = psutil.virtual_memory().percent #memória RAM utilizada em %

            mem_total = psutil.virtual_memory().total
            mem_total_gb = mem_total / conversor #memória em total em GB

            mem_disponivel = psutil.virtual_memory().available
            mem_disponivel_gb = mem_disponivel / conversor # memória disponível em GB

            #DISCO:
            disk_disponivel = psutil.disk_usage('/').free
            disk_disponivel_gb = disk_disponivel / conversor # disco livre em GB

            disk_percent = psutil.disk_usage('/').percent #ocupação do disco principal em %

            disk_total = psutil.disk_usage('/').total
            disk_total_gb = disk_total / conversor #disco total em GB

            #DATA E HORA:
            now = datetime.now()
            now_formated = now.strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow({'username': CONFIG["username"], 'data_hora': now_formated, 'cpu': cpu_percent, 'inte_cpu': cpu_interruption, 'ram_disponivel': mem_disponivel_gb, 'ram_total': mem_total_gb, 'ram': mem_percent, 'disco': disk_percent, 'disco_disponivel': disk_disponivel_gb, 'disco_total': disk_total_gb})

            print(f"Usuário: {CONFIG["username"]} | Data e Hora: {now_formated} | Uso de CPU: {cpu_percent}% | Interrupções de Hardware: {cpu_interruption} | RAM Disponível: {mem_disponivel_gb:.2f}GB | RAM Total: {mem_total_gb:.2f}GB | Uso de Memória RAM: {mem_percent}% | Uso de Disco: {disk_percent}% | Disco Disponível: {disk_disponivel_gb:.2f}GB | Disco Total: {disk_total_gb:.2f}GB")
            dados_linhas_csv -= 1

    
    with open(f'./processos_{CONFIG["username"]}.csv', 'w', newline='') as csvfile:
        fieldNames = ['Usuario', 'data_hora', 'PID', 'Nome' ,'Username']
        writer = csv.DictWriter(csvfile, fieldnames=fieldNames)
        writer.writeheader()
    
        while(processos_linhas_csv > 0): 
    
            #DATA E HORA:
            now = datetime.now()
            now_formated = now.strftime("%Y-%m-%d %H:%M:%S")

            #PROCESSOS
            for processos in psutil.process_iter(['pid', 'name', 'username']):
                info = processos.info
                if info['username'] is not None:
                    writer.writerow({'Usuario': CONFIG["username"], 'data_hora': now_formated, 'PID': info["pid"], 'Nome': info["name"], 'Username': info["username"]})
    
                    print(f"Usuário: {CONFIG["username"]} | Data e Hora: {now_formated} | PID: {info["pid"]} | Nome: {info["name"]} | Username: {info["username"]}")
                    processos_linhas_csv -= 1
                    

    print("Encerrando a Captura dos Dados.")

capturar_dados()