import csv 
import psutil 
from datetime import datetime

CONFIG = { #configuração do nome do usuario, linha escrita e qtd de linhas
    "username": "Servidor-B21X7M",
    "write_interval": 1,
    "csv_lines": 10
}

def capturar_dados():
    linhas_csv = CONFIG["csv_lines"]
    with open(f'./dados_processos_{CONFIG["username"]}.csv', 'w', newline='') as csvfile:
        fieldNames = ['Usuario', 'data_hora', 'PID', 'Nome' ,'Username']
        writer = csv.DictWriter(csvfile, fieldnames=fieldNames)
        writer.writeheader()
    
        while(linhas_csv > 0): #loop para criar cada linha
    
            #DATA E HORA:
            now = datetime.now()
            now_formated = now.strftime("%Y-%m-%d %H:%M:%S")

            #PROCESSOS
            for processos in psutil.process_iter(['pid', 'name', 'username']):
                info = processos.info
                if info['username'] is not None:
                    writer.writerow({'Usuario': CONFIG["username"], 'data_hora': now_formated, 'PID': info["pid"], 'Nome': info["name"], 'Username': info["username"]})
    
                    # print(f"Usuário: {CONFIG["username"]} | Data e Hora: {now_formated} | PID: {info["pid"]} | Nome: {info["name"]} | Username: {info["username"]}")
                    linhas_csv -= 1

capturar_dados()