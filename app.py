import os
import re
import uuid

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash

from database import db
from forms import (
    EliminarForm,
    PagoForm,
    PedidoForm,
    ProductoForm,
    UsuarioForm,
)
from mercadopago_service import crear_preferencia, obtener_pago
from models import ItemPedido, Pago, Pedido, Producto, Usuario

app = Flask(__name__)
app.config["SECRET_KEY"] = "clave-secreta-simulador-pagos"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///simulador.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
csrf = CSRFProtect(app)


def sembrar_datos():
    if Usuario.query.first() is None:
        db.session.add_all(
            [
                Usuario(
                    nombre="Ana Torres",
                    email="ana@correo.com",
                    password=generate_password_hash("123456"),
                ),
                Usuario(
                    nombre="Luis Gómez",
                    email="luis@correo.com",
                    password=generate_password_hash("123456"),
                ),
            ]
        )
    if Producto.query.first() is None:
        db.session.add_all(
            [
                Producto(nombre="Laptop", descripcion="Laptop 14 pulgadas", precio=850.0, stock=10),
                Producto(nombre="Mouse", descripcion="Mouse inalámbrico", precio=25.5, stock=50),
                Producto(nombre="Teclado", descripcion="Teclado mecánico", precio=75.0, stock=30),
                Producto(nombre="Monitor", descripcion="Monitor 24 pulgadas", precio=180.0, stock=15),
            ]
        )
    db.session.commit()


@app.context_processor
def utilidades():
    return {"delete_form": EliminarForm()}


@app.route("/")
def inicio():
    datos = {
        "usuarios": Usuario.query.count(),
        "productos": Producto.query.count(),
        "pedidos": Pedido.query.count(),
        "pagos": Pago.query.count(),
        "ingresos": db.session.query(db.func.coalesce(db.func.sum(Pago.monto), 0.0))
        .filter(Pago.estado == "Aprobado")
        .scalar(),
        "ultimos_pedidos": Pedido.query.order_by(Pedido.id.desc()).limit(5).all(),
    }
    return render_template("index.html", **datos)


# ---------------- Productos ----------------


@app.route("/productos")
def productos():
    lista = Producto.query.order_by(Producto.nombre).all()
    return render_template("productos/lista.html", productos=lista)


@app.route("/productos/nuevo", methods=["GET", "POST"])
def producto_nuevo():
    form = ProductoForm()
    if form.validate_on_submit():
        producto = Producto(
            nombre=form.nombre.data,
            descripcion=form.descripcion.data,
            precio=form.precio.data,
            stock=form.stock.data,
        )
        db.session.add(producto)
        db.session.commit()
        flash("Producto creado correctamente.", "exito")
        return redirect(url_for("productos"))
    return render_template("productos/formulario.html", form=form, titulo="Nuevo producto")


@app.route("/productos/<int:producto_id>/editar", methods=["GET", "POST"])
def producto_editar(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    form = ProductoForm(obj=producto)
    if form.validate_on_submit():
        producto.nombre = form.nombre.data
        producto.descripcion = form.descripcion.data
        producto.precio = form.precio.data
        producto.stock = form.stock.data
        db.session.commit()
        flash("Producto actualizado.", "exito")
        return redirect(url_for("productos"))
    return render_template("productos/formulario.html", form=form, titulo="Editar producto")


@app.route("/productos/<int:producto_id>/eliminar", methods=["POST"])
def producto_eliminar(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    if producto.items:
        flash("No se puede eliminar: el producto tiene pedidos asociados.", "error")
        return redirect(url_for("productos"))
    db.session.delete(producto)
    db.session.commit()
    flash("Producto eliminado.", "exito")
    return redirect(url_for("productos"))


# ---------------- Usuarios ----------------


@app.route("/usuarios")
def usuarios():
    lista = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("usuarios/lista.html", usuarios=lista)


@app.route("/usuarios/nuevo", methods=["GET", "POST"])
def usuario_nuevo():
    form = UsuarioForm()
    if form.validate_on_submit():
        if Usuario.query.filter_by(email=form.email.data).first():
            flash("Ya existe un usuario con ese email.", "error")
        else:
            usuario = Usuario(
                nombre=form.nombre.data,
                email=form.email.data,
                password=generate_password_hash(form.password.data),
            )
            db.session.add(usuario)
            db.session.commit()
            flash("Usuario creado correctamente.", "exito")
            return redirect(url_for("usuarios"))
    return render_template("usuarios/formulario.html", form=form, titulo="Nuevo usuario")


@app.route("/usuarios/<int:usuario_id>/eliminar", methods=["POST"])
def usuario_eliminar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuario eliminado junto con sus pedidos.", "exito")
    return redirect(url_for("usuarios"))


# ---------------- Pedidos ----------------


def _preparar_pedido_form(form):
    form.usuario_id.choices = [(u.id, u.nombre) for u in Usuario.query.order_by(Usuario.nombre)]
    choices = [(0, "— Seleccione un producto —")] + [
        (p.id, f"{p.nombre} (${p.precio:.2f})") for p in Producto.query.order_by(Producto.nombre)
    ]
    if request.method == "POST":
        indices = set()
        for clave in request.form:
            coincidencia = re.match(r"items-(\d+)-", clave)
            if coincidencia:
                indices.add(int(coincidencia.group(1)))
        while len(form.items) <= max(indices, default=0):
            form.items.append_entry()
    for item in form.items:
        item.producto_id.choices = choices
    return form


@app.route("/pedidos")
def pedidos():
    lista = Pedido.query.order_by(Pedido.id.desc()).all()
    return render_template("pedidos/lista.html", pedidos=lista)


@app.route("/pedidos/nuevo", methods=["GET", "POST"])
def pedido_nuevo():
    form = _preparar_pedido_form(PedidoForm())
    if form.validate_on_submit():
        pedido = Pedido(usuario_id=form.usuario_id.data, estado="Pendiente")
        db.session.add(pedido)
        agregados = 0
        for item in form.items:
            if item.producto_id.data == 0 or not item.cantidad.data:
                continue
            producto = Producto.query.get(item.producto_id.data)
            if producto is None:
                continue
            if item.cantidad.data > producto.stock:
                flash(f"Stock insuficiente de {producto.nombre}.", "error")
                return redirect(url_for("pedido_nuevo"))
            detalle = ItemPedido(
                pedido=pedido,
                producto=producto,
                cantidad=item.cantidad.data,
                precio_unitario=producto.precio,
            )
            db.session.add(detalle)
            producto.stock -= item.cantidad.data
            agregados += 1
        if agregados == 0:
            db.session.rollback()
            flash("Debes agregar al menos un producto.", "error")
            return redirect(url_for("pedido_nuevo"))
        pedido.calcular_total()
        db.session.commit()
        flash("Pedido creado correctamente.", "exito")
        return redirect(url_for("pedido_detalle", pedido_id=pedido.id))
    return render_template("pedidos/formulario.html", form=form)


@app.route("/pedidos/<int:pedido_id>")
def pedido_detalle(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    pago_form = PagoForm(monto=pedido.total)
    return render_template("pedidos/detalle.html", pedido=pedido, pago_form=pago_form)


@app.route("/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
def pedido_cancelar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.estado == "Pagado":
        flash("No se puede cancelar un pedido pagado.", "error")
        return redirect(url_for("pedido_detalle", pedido_id=pedido.id))
    for item in pedido.items:
        item.producto.stock += item.cantidad
    pedido.estado = "Cancelado"
    db.session.commit()
    flash("Pedido cancelado y stock restaurado.", "exito")
    return redirect(url_for("pedido_detalle", pedido_id=pedido.id))


@app.route("/pedidos/<int:pedido_id>/eliminar", methods=["POST"])
def pedido_eliminar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.estado not in ("Pagado", "Cancelado"):
        for item in pedido.items:
            item.producto.stock += item.cantidad
    db.session.delete(pedido)
    db.session.commit()
    flash("Pedido eliminado.", "exito")
    return redirect(url_for("pedidos"))


# ---------------- Pagos (simulados) ----------------


@app.route("/pedidos/<int:pedido_id>/pagar", methods=["POST"])
def pedido_pagar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    form = PagoForm()
    if pedido.estado in ("Pagado", "Cancelado"):
        flash(f"No se puede cobrar un pedido {pedido.estado.lower()}.", "error")
        return redirect(url_for("pedido_detalle", pedido_id=pedido.id))
    if form.validate_on_submit():
        pago = Pago(
            pedido=pedido,
            monto=form.monto.data,
            metodo=form.metodo.data,
            estado=form.resultado.data,
            referencia=uuid.uuid4().hex[:10].upper(),
        )
        db.session.add(pago)
        if form.resultado.data == "Aprobado":
            pedido.estado = "Pagado"
            flash(f"Pago aprobado por ${form.monto.data:.2f} ({form.metodo.data}).", "exito")
        else:
            pedido.estado = "Rechazado"
            flash("Pago rechazado. El pedido queda pendiente de cobro.", "error")
        db.session.commit()
    else:
        flash("Datos de pago inválidos.", "error")
    return redirect(url_for("pedido_detalle", pedido_id=pedido.id))


@app.route("/pagos")
def pagos():
    lista = Pago.query.order_by(Pago.id.desc()).all()
    return render_template("pagos/lista.html", pagos=lista)


# ---------------- Mercado Pago ----------------


def _registrar_pago_mp(payment_id):
    """Consulta el pago a Mercado Pago y actualiza Pago y Pedido. Es idempotente."""
    info = obtener_pago(payment_id)
    if not info:
        return None
    try:
        pedido = db.session.get(Pedido, int(info.get("external_reference") or 0))
    except ValueError:
        pedido = None
    if pedido is None:
        return None

    estado = {"approved": "Aprobado", "rejected": "Rechazado"}.get(info["status"], "Pendiente")

    pago = Pago.query.filter_by(referencia=str(payment_id)).first()
    if pago is None:
        pago = Pago(
            pedido=pedido,
            monto=info["transaction_amount"],
            metodo="Mercado Pago",
            estado=estado,
            referencia=str(payment_id),
        )
        db.session.add(pago)
    else:
        pago.estado = estado

    if estado == "Aprobado":
        # Si el pedido fue cancelado, el stock ya se restauró: el pago queda
        # registrado como Aprobado para poder reembolsarlo desde Mercado Pago.
        if pedido.estado != "Cancelado":
            pedido.estado = "Pagado"
    elif estado == "Rechazado" and pedido.estado not in ("Pagado", "Cancelado"):
        pedido.estado = "Rechazado"
    db.session.commit()
    return pedido


@app.route("/pedidos/<int:pedido_id>/mercadopago", methods=["POST"])
def pedido_mercadopago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.estado in ("Pagado", "Cancelado"):
        flash(f"No se puede pagar un pedido {pedido.estado.lower()}.", "error")
        return redirect(url_for("pedido_detalle", pedido_id=pedido.id))
    base_url = (os.environ.get("BASE_URL") or request.url_root).rstrip("/")
    try:
        pref = crear_preferencia(pedido, base_url)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("pedido_detalle", pedido_id=pedido.id))
    return redirect(pref["init_point"])


@app.route("/pagos/retorno")
def pagos_retorno():
    payment_id = request.args.get("payment_id") or request.args.get("collection_id")
    pedido = _registrar_pago_mp(payment_id) if payment_id and payment_id != "null" else None
    if pedido is None:
        ref = request.args.get("external_reference")
        flash("No pudimos confirmar el pago todavía.", "error")
        if ref and ref.isdigit():
            return redirect(url_for("pedido_detalle", pedido_id=int(ref)))
        return redirect(url_for("pedidos"))
    if pedido.estado == "Pagado":
        flash("¡Pago aprobado con Mercado Pago!", "exito")
    else:
        flash(f"El pago quedó en estado: {pedido.estado}.", "error")
    return redirect(url_for("pedido_detalle", pedido_id=pedido.id))


@app.route("/pagos/webhook", methods=["POST"])
@csrf.exempt
def pagos_webhook():
    body = request.get_json(silent=True) or {}
    tipo = body.get("type") or request.args.get("type") or request.args.get("topic")
    payment_id = (
        (body.get("data") or {}).get("id")
        or request.args.get("data.id")
        or request.args.get("id")
    )
    if tipo == "payment" and payment_id:
        _registrar_pago_mp(payment_id)
    return jsonify(ok=True), 200


# ---------------- Utilidades ----------------


@app.cli.command("init-db")
def init_db():
    db.create_all()
    sembrar_datos()
    print("Base de datos inicializada con datos de ejemplo.")


with app.app_context():
    db.create_all()
    sembrar_datos()


if __name__ == "__main__":
    app.run(debug=True)