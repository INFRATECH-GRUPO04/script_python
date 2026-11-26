# script_python

## Gerador de dados simulados

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha DB_* e S3_*
python gerar_dados_simulados.py
```

O script consulta os servidores ativos no MySQL, monta 30 dias de capturas por
servidor e envia os CSVs diretamente para `01-bronze/` no S3. Não grava arquivos
locais. Depois da execução, dispare manualmente as Lambdas bronze→silver e
silver→gold para atualizar as dashboards.

O acesso ao S3 usa a cadeia padrão do `boto3`: na EC2 com IAM Role, deixe as
credenciais do `.env` comentadas; fora dela, preencha
`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (e `AWS_SESSION_TOKEN` se for
temporário) **ou** `AWS_PROFILE` com `AWS_SHARED_CREDENTIALS_FILE` /
`AWS_CONFIG_FILE`. Nunca preencha só uma das chaves. `AWS_REGION` e
`AWS_DEFAULT_REGION` definem a região (padrão `us-east-1`).
