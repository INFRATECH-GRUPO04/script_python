import csv
import time as t

dados = [arq for arq in __import__('os').listdir('.') if arq.endswith('.csv')]

limite = 0
def conversaoGB(numero):
    return f"{numero / 1024**3:.2f} GB"

print(f"""
==========================================================================================
    ######  ###    ##  ######  ######     ####      ########  #######    ####  ##   ##
      ##    ## #   ##  ##      ##    #  ##    ##       ##     ##       ##      ##   ##
      ##    ##  #  ##  ####    ######   ##    ##       ##     #####    ##      #######
      ##    ##   # ##  ##      ##  ##   ########       ##     ##       ##      ##   ##
    ######  ##    ###  ##      ##    #  ##    ##       ##     #######    ####  ##   ##
==========================================================================================
""")
t.sleep(3)
print("\n" * 100)

escolha = []

while limite < 3:
    print("""
1. CPU      2. RAM      3. Disco        4. Todos os componentes
""")
    componente = int(input("Escolha o componente: "))
    if componente == 4:
        escolha.append(componente)
        break
    elif componente > 4 or componente < 1:
        print("Não existe este componente, tente novamente")
        continue
    else:
        escolha.append(componente)
        limite +=1

    continuar = str(input("Escolher outro componente (responda com s ou n): "))
    if continuar == "s":
        continue
    else:
        break

print(escolha)



for arquivo in dados:
    t.sleep(2)
    print(f"\n==========================================================================================")
    print(arquivo, "\n")
    try:
        with open(arquivo, 'r') as arquivo:
            leitor = csv.reader(arquivo)
            
            cabecalho = next(leitor)
            qtd_colunas = len(cabecalho)
            linhas = list(leitor)
            qtd_linhas = len(linhas)

            print("Ultimo valor")

            for indice in range(0, qtd_colunas):
                ultima = linhas[-1]
                ultimo_valor = ultima[indice]

                def convercao():
                    if indice == 3 or indice == 4 or indice == 6 or indice == 7:
                        numerico = float(ultimo_valor)
                        print(f"{cabecalho[indice]}: {conversaoGB(numerico)}\n")
                    else:
                        print(f"{cabecalho[indice]}: {ultimo_valor}\n")

                def estatistica():
                    valores_coluna = [float(linha[indice]) for linha in linhas if len(linha) > indice and linha[indice] != '']

                    v_max = max(valores_coluna)
                    v_min = min(valores_coluna)
                    v_media = sum(valores_coluna) / len(valores_coluna)

                    if indice == 3 or indice == 4 or indice == 6 or indice == 7:
                        print(f"Valor máximo: {conversaoGB(v_max)}")
                        print(f"Valor mínimo: {conversaoGB(v_min)} ")
                        print(f"Média: :{conversaoGB(v_media)} ")
                    else:
                        print(f"Valor máximo: :{v_max}")
                        print(f"Valor mínimo: :{v_min}")
                        print(f"Média: :{v_media}")

                for compo in escolha:

                    if compo == 1:
                        if indice == 1 or indice==2:
                            convercao()
                        else:
                            continue
                        estatistica()
                    elif compo == 2:
                        if indice == 5 or indice == 3 or indice == 4:
                            convercao()
                        else:
                            continue
                        estatistica()
                    elif compo == 3:
                        if indice == 6 or indice == 7 or indice == 8:
                            convercao()
                        else:
                            continue
                        estatistica()
                    else:
                        convercao()
                        estatistica()

    except FileNotFoundError:
        print(f"Arquivo {arquivo} não encontrado.")

print(f"\n==========================================================================================")