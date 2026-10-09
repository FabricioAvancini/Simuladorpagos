from datetime import datetime

from database import db


class Usuario(db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    creado = db.Column(db.DateTime, default=datetime.utcnow)

    pedidos = db.relationship(
        "Pedido",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<Usuario {self.nombre}>"


class Producto(db.Model):
    __tablename__ = "producto"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(250))
    precio = db.Column(db.Float, nullable=False, default=0.0)
    stock = db.Column(db.Integer, nullable=False, default=0)

    items = db.relationship("ItemPedido", back_populates="producto", lazy=True)

    def __repr__(self):
        return f"<Producto {self.nombre}>"


class Pedido(db.Model):
    __tablename__ = "pedido"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    total = db.Column(db.Float, nullable=False, default=0.0)
    estado = db.Column(db.String(50), default="Pendiente")
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario", back_populates="pedidos")
    items = db.relationship(
        "ItemPedido",
        back_populates="pedido",
        cascade="all, delete-orphan",
        lazy=True,
    )
    pagos = db.relationship(
        "Pago",
        back_populates="pedido",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def calcular_total(self):
        self.total = round(sum(item.subtotal() for item in self.items), 2)
        return self.total

    def __repr__(self):
        return f"<Pedido {self.id} - {self.estado}>"


class ItemPedido(db.Model):
    __tablename__ = "item_pedido"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float, nullable=False, default=0.0)

    pedido = db.relationship("Pedido", back_populates="items")
    producto = db.relationship("Producto", back_populates="items")

    def subtotal(self):
        return self.precio_unitario * self.cantidad


class Pago(db.Model):
    __tablename__ = "pago"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False, default=0.0)
    metodo = db.Column(db.String(50))
    estado = db.Column(db.String(50), default="Pendiente")
    referencia = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    pedido = db.relationship("Pedido", back_populates="pagos")

    def __repr__(self):
        return f"<Pago {self.id} - {self.estado}>"
