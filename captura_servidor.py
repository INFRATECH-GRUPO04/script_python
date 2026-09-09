import csv
import time as t
import psutil as p

limite = 0

print(f"""
==========================================================================================
    ######  ###    ##  ######  ######     ####      ########  #######    ####  ##   ##
      ##    ## #   ##  ##      ##    #  ##    ##       ##     ##       ##      ##   ##
      ##    ##  #  ##  ####    ######   ##    ##       ##     #####    ##      #######
      ##    ##   # ##  ##      ##  ##   ########       ##     ##       ##      ##   ##
    ######  ##    ###  ##      ##    #  ##    ##       ##     #######    ####  ##   ##
==========================================================================================
""")
t.sleep(5)
print("\n"* 100)

print("==========================================================================================")
Server = input("Qual o nome do servidor: ")
print("==========================================================================================")


# Validação para ver se o arquivo existe
try:
    with open(f'{Server}.csv', 'r'):
        pass
except FileNotFoundError:
    with open(f'{Server}.csv', 'w', newline='') as arquivo:
            csv.writer(arquivo).writerow(["TimeStamp", "CPU%", "InteCPU", "TotalRAM", "DisponivelRAM", "RAM%", "TotalDisco", "DisponivelDisco", "Disco%"])

t.sleep(1);
print("Data e Hora, %CPU, InteCPU, TotalRAM, DisponivelRAM, RAM%, TotalDisco, DisponivelDisco, Disco%")

while limite <= 5:
    timestamp = t.strftime('%d/%m/%Y %H:%M:%S')
    per_cpu = p.cpu_percent(interval=1)
    InterruptionCPU = p.cpu_stats().interrupts
    TotalRAM = p.virtual_memory().total
    DisponivelRAM = p.virtual_memory().available
    per_ram = p.virtual_memory().percent
    TotalDisco = p.disk_usage('C://').total
    DisponivelDisco = p.disk_usage('C://').used
    per_Disco = p.disk_usage('C://').percent
    
    with open(f'{Server}.csv', 'a', newline='') as arquivo:
        csv.writer(arquivo).writerow([timestamp, per_cpu, InterruptionCPU, TotalRAM, DisponivelRAM, per_ram, TotalDisco, DisponivelDisco, per_Disco])
    print(timestamp, per_cpu, InterruptionCPU, TotalRAM, DisponivelRAM, per_ram, TotalDisco, DisponivelDisco, per_Disco)
    limite += 1
    t.sleep(3)
