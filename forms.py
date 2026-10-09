from flask_wtf import FlaskForm
from wtforms import (
    FieldList,
    FloatField,
    FormField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, NumberRange


class ProductoForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(message="El nombre es obligatorio")])
    descripcion = StringField("Descripción")
    precio = FloatField(
        "Precio", validators=[DataRequired(), NumberRange(min=0, message="El precio no puede ser negativo")]
    )
    stock = IntegerField(
        "Stock", validators=[DataRequired(), NumberRange(min=0, message="El stock no puede ser negativo")]
    )
    submit = SubmitField("Guardar")


class UsuarioForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(message="El nombre es obligatorio")])
    email = StringField("Email", validators=[DataRequired(), Email(message="Email inválido")])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    submit = SubmitField("Guardar")


class ItemPedidoForm(FlaskForm):
    class Meta:
        csrf = False

    producto_id = SelectField("Producto", coerce=int)
    cantidad = IntegerField(
        "Cantidad", validators=[DataRequired(), NumberRange(min=1, message="Mínimo 1")], default=1
    )


class PedidoForm(FlaskForm):
    usuario_id = SelectField("Usuario", coerce=int, validators=[DataRequired()])
    items = FieldList(FormField(ItemPedidoForm), min_entries=1)
    submit = SubmitField("Crear pedido")


class PagoForm(FlaskForm):
    metodo = SelectField(
        "Método de pago",
        choices=[
            ("Tarjeta de crédito", "Tarjeta de crédito"),
            ("Tarjeta de débito", "Tarjeta de débito"),
            ("PayPal", "PayPal"),
            ("Transferencia bancaria", "Transferencia bancaria"),
            ("Efectivo", "Efectivo"),
        ],
    )
    monto = FloatField(
        "Monto a cobrar", validators=[DataRequired(), NumberRange(min=0.01, message="Monto inválido")]
    )
    resultado = SelectField(
        "Resultado simulado",
        choices=[("Aprobado", "Aprobado"), ("Rechazado", "Rechazado")],
    )
    submit = SubmitField("Procesar pago")


class EliminarForm(FlaskForm):
    submit = SubmitField("Eliminar")
