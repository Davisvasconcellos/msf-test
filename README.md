# MSF Test – Desenvolvimento (Respostas e Demos)

Este repositório contém o resultado do teste técnico para a área de desenvolvimento da **MSF**.  
O projeto reúne:
- As **respostas escritas** das perguntas técnicas
- Uma **aplicação prática em Flask** com demos interativas que materializam essas respostas

Versão live (Render – pode demorar até ~50 segundos para acordar o serviço):

`https://msf-test.onrender.com/responses`

---

## Visão Geral da Aplicação

A aplicação é um backend Flask com páginas HTML renderizadas via Jinja, focada em demonstrar conceitos de:
- OAuth 2.0 e tokens JWT
- Consultas SQL avançadas (CTE recursiva, window functions)
- Boas práticas de atualização em lote em banco relacional
- Consumo de API REST com idempotência e retries
- Normalização de dados e tratamento de entradas inconsistentes

As páginas principais são:
- `/responses`: página única com todas as respostas detalhadas das perguntas
- `/demo/1`: fluxo OAuth 2.0 + PKCE (demonstração conceitual)
- `/demo/3`: CTE recursiva para exploração de relacionamentos em grafo
- `/demo/5`: atualização de pedidos PENDING → PROCESSED em lote
- `/demo/6`: consumo de API mock (JSONPlaceholder) com tratamento de erros
- `/demo/7`: normalização de usuários
- `/demo/8`: deep key map / transformação de estruturas aninhadas

---

## Tecnologias Utilizadas

- **Linguagem**: Python 3
- **Framework Web**: Flask
- **Servidor WSGI**: Gunicorn (produção – Render)
- **ORM/Conexão**: SQLAlchemy
- **Banco de Dados (produção)**: MariaDB (compatível MySQL)
- **Hospedagem**: Render (Web Service)
- **Outros**:
  - `python-dotenv` para carregar variáveis de ambiente em desenvolvimento
  - `requests` para consumo de API mock
  - `PyJWT` + `cryptography` para manipulação de JWT

Importante: na aplicação prática foi utilizada uma instância **MariaDB** em vez de SQL Server, mantendo a mesma modelagem conceitual de pedidos e relacionamentos.

---

## Dados de Exemplo e Tabelas

Todos os dados são **fictícios**, criados apenas para a finalidade da prova e das demos.

Ao iniciar as demos de banco, o código cria e povoa automaticamente duas tabelas:

### Tabela `Sales_Orders`

Representa pedidos de venda, usada principalmente nos demos de:
- Atualização em lote (SQL Update – `/demo/5`)
- Consumo de API mock de pedidos (demo 6, reaproveitando a mesma tabela)

Estrutura (MariaDB):

- `OrderID` – `INT`, chave primária, `AUTO_INCREMENT`
- `OrderDate` – `DATE`, não nulo
- `Status` – `VARCHAR(20)`, não nulo  
  Valores usados nos exemplos: `PENDING`, `PROCESSED`
- `CustomerName` – `VARCHAR(100)`, não nulo
- `Amount` – `DECIMAL(10,2)`, não nulo
- Índice composto: `idx_status_orderdate (Status, OrderDate)` para:
  - filtrar rápido pelos pedidos `PENDING`
  - ordenar por data em consultas analíticas

Ao detectar a tabela vazia, o código insere um conjunto de pedidos fictícios distribuídos ao longo dos últimos dias, com combinação de estados PENDING/PROCESSED e valores variados, para poder:
- testar atualização em lote (SQL)
- simular rotinas de processamento de fila de pedidos

### Tabela `Relacionamentos`

Representa relacionamentos direcionados entre usuários, usada na demo de **CTE recursiva** (`/demo/3`).

Estrutura (MariaDB):

- `id` – `INT`, chave primária, `AUTO_INCREMENT`
- `id_origem` – `INT`, não nulo  
  Identifica o usuário de origem do relacionamento
- `id_destino` – `INT`, não nulo  
  Identifica o usuário de destino
- `tipo_relacao` – `VARCHAR(50)`, não nulo  
  Ex.: `amigo`, `seguidor`, `colega`
- Índices:
  - `idx_rel_origem (id_origem)`
  - `idx_rel_destino (id_destino)`

A semente de dados cria um pequeno grafo de usuários (1 a 8) com diferentes tipos de relacionamento para:
- explorar caminhos recursivos (profundidade limitada)
- detectar ciclos
- calcular métricas por usuário (entradas, saídas, total de conexões)

---

## Variáveis de Ambiente

O projeto usa variáveis de ambiente para separar configuração de código:

- `DATABASE_URL`  
  String de conexão para o banco MariaDB/MySQL.  
  Exemplo (conceitual):
  `mysql://usuario:senha@host:3306/nome_banco`

- `SECRET_KEY`  
  Chave de sessão do Flask (usada para cookies de sessão e flash messages).

- `API_TOKEN`  
  Token fictício usado nas demos de consumo de API.

Em ambiente local, essas variáveis podem ser definidas em um arquivo `.env` (carregado via `python-dotenv`).  
Em produção (Render), são configuradas diretamente nas **Environment Variables** do serviço.

---

## Como Rodar Localmente

Pré-requisitos:
- Python 3 instalado
- Acesso a um banco MariaDB/MySQL (pode ser local ou remoto)

Passos:

1. Clonar o repositório:

```bash
git clone https://github.com/Davisvasconcellos/msf-test.git
cd msf-test
```

2. Criar e ativar um ambiente virtual (opcional, mas recomendado):

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate     # Windows
```

3. Instalar dependências:

```bash
pip install -r requirements.txt
```

4. Configurar variáveis de ambiente (exemplo usando `.env`):

Crie um arquivo `.env` na raiz com conteúdo semelhante a:

```env
DATABASE_URL=mysql://usuario:senha@host:3306/nome_banco
SECRET_KEY=dev-secret-key-12345
API_TOKEN=token-ficticio-123
```

5. Iniciar a aplicação Flask:

```bash
python app.py
```

6. Acessar no navegador:
- http://localhost:5000/responses

---

## Deploy no Render (Resumo)

O projeto está configurado para ser executado como Web Service no Render:

- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

No Render, as variáveis `DATABASE_URL`, `SECRET_KEY` e `API_TOKEN` são preenchidas pelo painel, e o banco utilizado é um **MariaDB** compatível com a mesma modelagem do teste.

Devido ao cold start em serviços gratuitos/compartilhados, é normal que o primeiro acesso à URL:

`https://msf-test.onrender.com/responses`

demore **aproximadamente 50 segundos** para carregar até que o container seja iniciado.

---

## Autoria

- **Autor**: Davis Vasconcellos  
- **E-mail**: <davisvasconcellos@gmail.com>

---

## Observações Finais

- Todo o código e dados aqui presentes são destinados exclusivamente à avaliação técnica para a área de desenvolvimento da MSF.
- Os dados de clientes, pedidos e relacionamentos são **totalmente fictícios** e não representam informações reais.
- As respostas e demos buscam enfatizar:
  - boas práticas de segurança (OAuth 2.0, JWT, proteção de segredos)
  - modelagem e performance em SQL (CTEs, window functions, índices)
  - robustez no consumo de APIs externas (timeouts, retries, idempotência)

