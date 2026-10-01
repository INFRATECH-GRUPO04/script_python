import psutil
for processos in psutil.process_iter(['pid', 'name', 'username']):
            print(processos.info)