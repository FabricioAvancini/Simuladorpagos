"""Integración con Mercado Pago (Checkout Pro)."""
import os
import mercadopago


def _sdk():
    token = os.environ.get("MP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Falta MP_ACCESS_TOKEN en el archivo .env")
    return mercadopago.SDK(token)


def crear_preferencia(pedido, base_url):
    data = {
        "items": [
            {
                "title": item.producto.nombre,
                "quantity": item.cantidad,
                "unit_price": float(item.precio_unitario),
                "currency_id": "ARS",
            }
            for item in pedido.items
        ],
        "external_reference": str(pedido.id),
        "back_urls": {
            "success": f"{base_url}/pagos/retorno",
            "failure": f"{base_url}/pagos/retorno",
            "pending": f"{base_url}/pagos/retorno",
        },
        "auto_return": "approved",
        "notification_url": f"{base_url}/pagos/webhook",
    }
    resp = _sdk().preference().create(data)
    if resp["status"] not in (200, 201):
        raise RuntimeError(f"Mercado Pago rechazó la preferencia: {resp['response']}")
    return resp["response"]


def obtener_pago(payment_id):
    """Consulta el pago directo a Mercado Pago (no confiamos en la URL)."""
    resp = _sdk().payment().get(payment_id)
    return resp["response"] if resp["status"] == 200 else None