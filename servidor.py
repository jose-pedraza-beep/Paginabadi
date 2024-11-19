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

        # Aumentar el número de boletos del usuario actual
        sql_aumentar_boletos = "UPDATE usuarios SET boletosu = boletosu + %s WHERE id_user = %s"
        conexiondb.execute(sql_aumentar_boletos, (total_boletos, current_user.id))

        db.commit()
        return redirect(url_for('Peliculas'))
    except mysqlcon.Error as e:
        db.rollback()
        return f"Error al procesar la compra: {str(e)}", 500
    finally:
        conexiondb.close()

@app.route('/generar_qr', methods=['GET'])
@login_required
def generar_qr():
    try:
        conexiondb = db.cursor()

        # Obtener el número de boletos del usuario actual
        sql_boletos = "SELECT boletosu FROM usuarios WHERE id_user = %s"
        conexiondb.execute(sql_boletos, (current_user.id,))
        resultado = conexiondb.fetchone()

        if resultado and resultado[0] > 0:
            boletos = resultado[0]

            # Generar el contenido del QR
            contenido_qr = f"Usuario: {current_user.nombre}, Boletos: {boletos}"
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(contenido_qr)
            qr.make(fit=True)

            # Crear una imagen del QR
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf)
            buf.seek(0)

            # Eliminar los boletos del usuario después de generar el QR
            sql_eliminar_boletos = "UPDATE usuarios SET boletosu = 0 WHERE id_user = %s"
            conexiondb.execute(sql_eliminar_boletos, (current_user.id,))
            db.commit()

            # Enviar el QR al usuario
            return send_file(buf, mimetype='image/png', download_name='qr_boletos.png')
        else:
            return "No tienes boletos para comprobar.", 400
    except mysqlcon.Error as e:
        db.rollback()
        return f"Error al generar el QR: {str(e)}", 500
    finally:
        conexiondb.close()

if __name__ == '__main__':
    app.run()
