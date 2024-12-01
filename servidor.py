from flask import Flask, render_template, redirect, url_for, request, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector as mysqlcon
from werkzeug.security import generate_password_hash, check_password_hash
import os
import qrcode
import io

app = Flask(__name__)

# Configuración de base de datos
db = mysqlcon.connect(host="localhost", user="root", password="", database="login")

# Configuración de clave secreta
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(24)

# Configuración de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Clase de usuario para Flask-Login
class User(UserMixin):
    def __init__(self, idSesion, nameSesion, emailSesion, passSesion):
        self.id = idSesion
        self.nombre = nameSesion
        self.email = emailSesion
        self.passw = passSesion

    def get_id(self):
        return self.id

@login_manager.user_loader
def cargar_usuario(user_id):
    conexiondb = db.cursor()
    sql_user = f"SELECT id_user, nom_user, email_user, pass_user FROM usuarios WHERE id_user={user_id}"
    conexiondb.execute(sql_user)
    res_user = conexiondb.fetchone()
    conexiondb.close()

    if res_user:
        return User(res_user[0], res_user[1], res_user[2], res_user[3])
    return None

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user) 
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo_user = request.form['user_mail']
        pass_user = request.form['user_pass']

        conexiondb = db.cursor()
        sql_sesion = f"SELECT id_user, nom_user, email_user, pass_user FROM usuarios WHERE email_user='{correo_user}'"
        conexiondb.execute(sql_sesion)
        resultSesion = conexiondb.fetchone()
        conexiondb.close()
        
        if resultSesion:
            idResid, nameResname, emailResemail, passRespass = resultSesion
            if check_password_hash(passRespass, pass_user):
                logguser = User(idResid, nameResname, emailResemail, passRespass)
                login_user(logguser)
                return redirect(url_for('index'))
            else:
                msj = "Email o contraseña incorrectos"
                return render_template('login.html', msj=msj)
        else:
            msj = "Email o contraseña incorrectos"
            return render_template('login.html', msj=msj)
    else:
        msj = "Inicio de sesión"
        return render_template('login.html', msj=msj)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombreReg = request.form['reg_nombre']
        appellReg = request.form['reg_apell']
        telReg = request.form['reg_tel']
        emailReg = request.form['reg_mail']
        passReg = request.form['reg_pass']

        passHashed = generate_password_hash(passReg, method='pbkdf2', salt_length=16)

        conexiondb = db.cursor()
        sqlReg = "INSERT INTO usuarios(nom_user, app_user, tel_user, email_user, pass_user) VALUES(%s, %s, %s, %s, %s)"
        values = (nombreReg, appellReg, telReg, emailReg, passHashed)
        
        try:
            conexiondb.execute(sqlReg, values)
            db.commit()
            return redirect(url_for('login'))
        except mysqlcon.Error as e:
            db.rollback()
            msj = f"Ocurrió un error: {str(e)}"
            return render_template('register.html', msj=msj)
        finally:
            conexiondb.close()
    else:
        msj = "Registrar"
        return render_template("register.html", msj=msj)

@app.route('/Peliculas')
def Peliculas():
    conexiondb = db.cursor()
    sql_user = f"SELECT idp, nombrep, fechap, descripcionp, imgp, calificacionp,cupo FROM peliculas"
    conexiondb.execute(sql_user)
    res_user = conexiondb.fetchall()
    conexiondb.close()

    peliculas = [{'idp': campo[0], 'nombrep': campo[1], 'fechap': campo[2], 'descripcionp': campo[3], 'imgp': campo[4], 'calificacionp': campo[5],'cupo':campo[6]} for campo in res_user]
    return render_template("Peliculas.html", listap=peliculas)

@app.route('/compra_boletos/<int:pelicula_id>')
def compra_boletos(pelicula_id):
    conexiondb = db.cursor()
    sql_pelicula = f"SELECT idp, nombrep, fechap, descripcionp, imgp, calificacionp,cupo FROM peliculas WHERE idp={pelicula_id}"
    conexiondb.execute(sql_pelicula)
    pelicula = conexiondb.fetchone()
    conexiondb.close()

    if pelicula:
        pelicula_data = { 'idp': pelicula[0],'nombrep': pelicula[1], 'fechap': pelicula[2],'descripcionp': pelicula[3],'imgp': pelicula[4], 'calificacionp': pelicula[5],'cupo':[6]}
        return render_template("compra_boletos.html", pelicula=pelicula_data)
    else:
        return "Película no encontrada", 404

@app.route('/procesar_compra', methods=['POST'])
@login_required
def procesar_compra():
    pelicula_id = request.form.get('pelicula_id')
    cantidad_adulto = int(request.form.get('cantidad_adulto', 0))
    cantidad_ninos = int(request.form.get('cantidad_ninos', 0))
    cantidad_tercera = int(request.form.get('cantidad_tercera', 0))
    
    total_boletos = cantidad_adulto + cantidad_ninos + cantidad_tercera
    
    if total_boletos == 0:
        return "Debe seleccionar al menos un boleto.", 400

    try:
        conexiondb = db.cursor()

        # Disminuir cupo de la película
        sql_disminuir_cupo = "UPDATE peliculas SET cupo = cupo - %s WHERE idp = %s AND cupo >= %s"
        conexiondb.execute(sql_disminuir_cupo, (total_boletos, pelicula_id, total_boletos))

        if conexiondb.rowcount == 0:
            return "No hay suficientes lugares disponibles para esta película.", 400

        # Actualizar el número de boletos del usuario actual
        sql_aumentar_boletos = """
            UPDATE usuarios 
            SET boletosu = boletosu + %s, 
                boletos_adultos = boletos_adultos + %s,
                boletos_ninos = boletos_ninos + %s,
                boletos_tercera = boletos_tercera + %s
            WHERE id_user = %s
        """
        conexiondb.execute(sql_aumentar_boletos, (total_boletos, cantidad_adulto, cantidad_ninos, cantidad_tercera, current_user.id))

        db.commit()
        return redirect(url_for('Peliculas'))
    except mysqlcon.Error as e:
        db.rollback()
        return f"Error al procesar la compra: {str(e)}", 500
    finally:
        conexiondb.close()

import base64  # Asegúrate de importar este módulo

@app.route('/generar_qr', methods=['GET'])
@login_required
def generar_qr():
    try:
        conexiondb = db.cursor()

        # Obtener el número de boletos del usuario actual
        sql_boletos = "SELECT boletosu, boletos_adultos, boletos_ninos, boletos_tercera FROM usuarios WHERE id_user = %s"
        conexiondb.execute(sql_boletos, (current_user.id,))
        resultado = conexiondb.fetchone()

        if resultado and resultado[0] > 0:
            boletos, adultos, ninos, tercera = resultado

            # Generar el contenido del QR
            contenido_qr = (
                f"Usuario: {current_user.nombre}\n"
                f"Boletos totales: {boletos}\n"
                f"- Adultos: {adultos}\n"
                f"- Niños: {ninos}\n"
                f"- Tercera Edad: {tercera}"
            )
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(contenido_qr)
            qr.make(fit=True)

            # Crear una imagen del QR
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf)
            buf.seek(0)

            # Convertir la imagen a formato Base64
            qr_data = base64.b64encode(buf.getvalue()).decode('utf-8')

            # Eliminar los boletos del usuario después de generar el QR
            sql_eliminar_boletos = """
                UPDATE usuarios 
                SET boletosu = 0, boletos_adultos = 0, boletos_ninos = 0, boletos_tercera = 0
                WHERE id_user = %s
            """
            conexiondb.execute(sql_eliminar_boletos, (current_user.id,))
            db.commit()

            # Renderizar la plantilla HTML para mostrar el QR
            return render_template(
                'generar_qr.html', 
                qr_data=qr_data, 
                redirect_url=url_for('Peliculas')
            )
        else:
            return "No tienes boletos para comprobar.", 400
    except mysqlcon.Error as e:
        db.rollback()
        return f"Error al generar el QR: {str(e)}", 500
    finally:
        conexiondb.close()

@app.route('/mostrar_boletos', methods=['POST'])
def mostrar_boletos():
    datos_qr = request.form.get('datos_qr')
    if not datos_qr:
        return "No se recibieron datos del QR.", 400

    # Parsear los datos del QR para mostrar en pantalla
    detalles = datos_qr.replace('\n', '<br>')
    return render_template('mostrar_boletos.html', detalles=detalles)

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/Alimentos')
@login_required
def Alimentos():
    conexiondb = db.cursor()

    # Consulta para obtener la lista de alimentos
    sql_alimentos = """
        SELECT id, nombre, descripcion, precio, img_url 
        FROM alimentos
    """
    conexiondb.execute(sql_alimentos)
    res_alimentos = conexiondb.fetchall()

    # Consulta para obtener el carrito del usuario actual
    sql_carrito = """
        SELECT c.id, a.nombre, c.cantidad, (a.precio * c.cantidad) AS total
        FROM carrito c
        JOIN alimentos a ON c.id_alimento = a.id
        WHERE c.id_usuario = %s
    """
    conexiondb.execute(sql_carrito, (current_user.id,))
    res_carrito = conexiondb.fetchall()
    conexiondb.close()

    # Procesar datos de alimentos
    alimentos = [
        { 'id': campo[0],'nombre': campo[1],'descripcion': campo[2],'precio': campo[3],'img_url': campo[4]}
        for campo in res_alimentos
    ]

    # Procesar datos del carrito
    carrito = [
        { 'id': campo[0],'nombre': campo[1],'cantidad': campo[2],'total': campo[3]}
        for campo in res_carrito
    ]

    return render_template("Alimentos.html", alimentos=alimentos, carrito=carrito)


from flask import request, jsonify

@app.route('/agregar_carrito', methods=['POST'])
@login_required
def agregar_carrito():
    data = request.get_json()  # Leer datos enviados en formato JSON
    id_alimento = data.get('id_alimento')

    if not id_alimento:
        return jsonify({'error': 'ID del alimento no proporcionado'}), 400

    try:
        conexiondb = db.cursor()

        sql_verificar = """
            SELECT id, cantidad 
            FROM carrito 
            WHERE id_usuario = %s AND id_alimento = %s
        """
        conexiondb.execute(sql_verificar, (current_user.id, id_alimento))
        item = conexiondb.fetchone()

        if item:
            # Si existe, aumentar cantidad
            sql_actualizar = """
                UPDATE carrito 
                SET cantidad = cantidad + 1 
                WHERE id = %s
            """
            conexiondb.execute(sql_actualizar, (item[0],))
        else:
            # Si no existe, agregarlo al carrito
            sql_insertar = """
                INSERT INTO carrito (id_usuario, id_alimento, cantidad) 
                VALUES (%s, %s, 1)
            """
            conexiondb.execute(sql_insertar, (current_user.id, id_alimento))

        db.commit()
        return jsonify({'success': 'Producto agregado al carrito'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conexiondb.close()
@app.route('/modificar_cantidad_carrito', methods=['PUT'])
@login_required
def modificar_cantidad_carrito():
    data = request.get_json()
    id_carrito = data.get('id_carrito')
    nueva_cantidad = data.get('cantidad')

    if not id_carrito or not nueva_cantidad or int(nueva_cantidad) < 1:
        return jsonify({'error': 'Datos inválidos'}), 400

    try:
        conexiondb = db.cursor()

        # Actualizar la cantidad del producto en el carrito
        sql_actualizar = """
            UPDATE carrito 
            SET cantidad = %s 
            WHERE id = %s AND id_usuario = %s
        """
        conexiondb.execute(sql_actualizar, (nueva_cantidad, id_carrito, current_user.id))
        db.commit()

        return jsonify({'success': 'Cantidad modificada'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conexiondb.close()


@app.route('/eliminar_carrito/<int:id_carrito>', methods=['DELETE'])
@login_required
def eliminar_carrito(id_carrito):
    try:
        conexiondb = db.cursor()

        # Eliminar producto del carrito
        sql_eliminar = "DELETE FROM carrito WHERE id = %s AND id_usuario = %s"
        conexiondb.execute(sql_eliminar, (id_carrito, current_user.id))
        db.commit()

        return jsonify({'success': 'Producto eliminado del carrito'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conexiondb.close()




@app.route('/Proximamente')
def Proximamente():
    try:
        # Crear cursor para la conexión a la base de datos
        conexiondb = db.cursor()

        # Consulta para obtener las películas "próximamente"
        sql_proximamente = "SELECT nombrep, fechap, descripcionp, imgp FROM proximamente"
        conexiondb.execute(sql_proximamente)
        res_proximamente = conexiondb.fetchall()

        # Procesar los resultados en una lista de diccionarios
        proximas_peliculas = [
            {
                'nombrep': campo[0],
                'fechap': campo[1],
                'descripcionp': campo[2],
                'imgp': campo[3]
            }
            for campo in res_proximamente
        ]

        # Renderizar la plantilla y pasar los datos de las películas
        return render_template("Proximamente.html", listap=proximas_peliculas)
    except mysqlcon.Error as e:
        return f"Error al obtener películas: {str(e)}", 500
    finally:
        # Cerrar la conexión a la base de datos
        conexiondb.close()
@app.route("/Promociones")
def proxi():
    return render_template('Promociones.html')
if __name__ == '__main__':
    app.run()
