# script_python

## Gerador de dados simulados

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha DB_* e S3_*
python gerar_dados_simulados.py
```

O script consulta os servidores ativos no MySQL, monta 30 dias de capturas por
servidor e envia os CSVs diretamente para `01-bronze/` no S3 usando a IAM Role
da EC2. Não grava arquivos locais. Depois da execução, dispare manualmente as
Lambdas bronze→silver e silver→gold para atualizar as dashboards.
