# Order Processing

API simples de processamento assíncrono de pedidos construída com FastAPI e `asyncio`.

---

## Como rodar

**Pré-requisitos:** Python 3.11+

```bash
python3 -m venv venv
source bin/venv/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`.

Documentação interativa (Swagger): `http://localhost:8000/docs`

---

## Validação manual do fluxo

### 1. Criar um pedido

```bash
curl --location 'http://localhost:8000/orders' \
--header 'Content-Type: application/json' \
--data '{
    "customer_name": "João Silva",
    "items": [{"sku": "ABC-123", "quantity": 2}]
  }'
```

Resposta:

```json
{
    "id": "2664aaa8-1093-44f9-a459-ee2a87a5679c",
    "status": "CREATED",
    "created_at": "2026-06-11T19:49:12.742907-03:00"
}
```

Copie o `id` retornado para os próximos passos.

---

### 2. Consultar imediatamente após a criação

```bash
curl -s http://localhost:8000/orders/<id>
```

O status estará em `CREATED`, `PROCESSING_STOCK`, `STOCK_RESERVED`, `PROCESSING_TRANSPORT` ou `SENT_TO_TRANSPORT`, dependendo da velocidade de resposta.

---

### 3. Aguardar ~3 segundos e consultar novamente

```bash
sleep 3 && curl -s http://localhost:8000/orders/<id>
```

Resposta esperada:

```json
{
    "id": "2664aaa8-1093-44f9-a459-ee2a87a5679c",
    "customer_name": "João Silva",
    "items": [
        {
            "sku": "ABC-123",
            "quantity": 2
        }
    ],
    "status": "SENT_TO_TRANSPORT",
    "created_at": "2026-06-11T19:49:12.742229-03:00",
    "updated_at": "2026-06-11T19:49:14.744421-03:00",
    "timeline": [
        {
            "status": "CREATED",
            "at": "2026-06-11T19:49:12.742229-03:00"
        },
        {
            "status": "PROCESSING_STOCK",
            "at": "2026-06-11T19:49:12.743802-03:00"
        },
        {
            "status": "STOCK_RESERVED",
            "at": "2026-06-11T19:49:13.743810-03:00"
        },
        {
            "status": "PROCESSING_TRANSPORT",
            "at": "2026-06-11T19:49:13.744301-03:00"
        },
        {
            "status": "SENT_TO_TRANSPORT",
            "at": "2026-06-11T19:49:14.744421-03:00"
        }
    ]
}
```

---

### 4. Consultar a timeline de um pedido

```bash
curl --location 'http://localhost:8000/orders/2664aaa8-1093-44f9-a459-ee2a87a5679c/timeline'
```

Resposta esperada:
```json
[
    {
        "status": "CREATED",
        "at": "2026-06-11T19:49:12.742229-03:00"
    },
    {
        "status": "PROCESSING_STOCK",
        "at": "2026-06-11T19:49:12.743802-03:00"
    },
    {
        "status": "STOCK_RESERVED",
        "at": "2026-06-11T19:49:13.743810-03:00"
    },
    {
        "status": "PROCESSING_TRANSPORT",
        "at": "2026-06-11T19:49:13.744301-03:00"
    },
    {
        "status": "SENT_TO_TRANSPORT",
        "at": "2026-06-11T19:49:14.744421-03:00"
    }
]
```


---

### 5. Consultar um pedido inexistente (deve retornar 404)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/orders/00000000-0000-0000-0000-000000000000
```

Resposta esperada: `404`

---

## Fluxo de status

```
CREATED
  → PROCESSING_STOCK    (estoque inicia o processamento)
  → STOCK_RESERVED      (estoque separado com sucesso)
  → PROCESSING_TRANSPORT (transporte inicia o envio)
  → SENT_TO_TRANSPORT   (pedido despachado)
```

Em caso de erro em qualquer etapa, o status é atualizado para `FAILED`.