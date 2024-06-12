from flask import make_response,Flask,render_template,request,redirect,url_for,flash,session
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap5 #pip install bootstrap-flask
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import LoginManager,UserMixin,login_user,login_required,logout_user,current_user
import email_validator
from forms import LoginForm,BrandForm,CategoryForm,UpdateBrandForm,UpdateCategoryForm
from datetime import date,datetime
from sqlalchemy.orm import relationship
import os
import secrets
import json
from functools import wraps
import pdfkit
import stripe


publishable_key=os.environ.get("PUBLISH_KEY")
stripe.api_key=os.environ.get("API_KEY")


app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("FLASK_KEY")

bootstrap=Bootstrap5(app)

db=SQLAlchemy()
app.config["SQLALCHEMY_DATABASE_URI"]=os.environ.get("DB_URI","sqlite:///myshop.db")
db.init_app(app)

login_manager=LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id==user_id)).scalar()


class User(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True)
    firstname=db.Column(db.String(50),unique=False,nullable=False)
    lastname = db.Column(db.String(50), unique=False, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email=db.Column(db.String(50),unique=True,nullable=False)
    password=db.Column(db.String(50),unique=False,nullable=False)
    address=db.Column(db.Text,nullable=False)
    state=db.Column(db.String(50),nullable=False)
    country=db.Column(db.String(150),nullable=False)
    zipcode=db.Column(db.Integer,nullable=False)
    profile_pic=db.Column(db.String(150),unique=False,nullable=False)


class Brand(db.Model):
    __tablename__="brands"
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(30),unique=True,nullable=False)
    products=relationship("Product",back_populates="brand_name")


class Category(db.Model):
    __tablename__="categories"
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(30),unique=True,nullable=False)
    products=relationship("Product",back_populates="category_name")


class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(100),nullable=False,unique=True)
    price=db.Column(db.Numeric(10,2),nullable=False)
    discount=db.Column(db.Integer,nullable=True)
    stock=db.Column(db.Integer,nullable=False)
    description=db.Column(db.Text,nullable=False)
    colors=db.Column(db.Text,nullable=False)
    brand_id=db.Column(db.Integer,db.ForeignKey("brands.id"))
    category_id=db.Column(db.Integer,db.ForeignKey("categories.id"))
    image_1=db.Column(db.String(150),nullable=False)
    image_2 = db.Column(db.String(150), nullable=False)
    image_3 = db.Column(db.String(150), nullable=False)
    brand_name=relationship("Brand",back_populates="products")
    category_name=relationship("Category",back_populates="products")


class ItemsDict(db.TypeDecorator):
    impl = db.Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return "{}"
        else:
            return json.dumps(value)

    def process_result_value(self,value,dialect):
        if value is None:
            return "{}"
        else:
            return json.loads(value)


class Order(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    invoice=db.Column(db.String(20),unique=True,nullable=False)
    status=db.Column(db.String(20),nullable=False,default="pending")
    date_created=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    customer_id=db.Column(db.Integer,nullable=False)
    items=db.Column(ItemsDict)


with app.app_context():
    db.create_all()


def MergedItemsDict(dict1,dict2):
    if isinstance(dict1,dict) and isinstance(dict2,dict):
        items = dict(list(dict1.items()) + list(dict2.items()))
        return items
    return False


@app.route('/',methods=["GET","POST"])
def login():
    current_yr=date.today().year
    form=LoginForm()
    if form.validate_on_submit():
        user=db.session.execute(db.select(User).where(User.email==form.email.data)).scalar()
        if user:
            if not check_password_hash(user.password,form.password.data):
                flash("Sorry, wrong password. Pls try again.")
                return render_template("index.html", form=form, is_error=True)
            else:
                login_user(user)
                flash(f"Welcome, {user.username}! Your have successfully logged in.")
                return redirect(url_for("home"))
        else:
            flash("Oops! Wrong email and password.")
            return render_template("index.html",form=form,is_error=True)
    return render_template("index.html",form=form,year=current_yr)


@app.route("/admin_page")
def admin():
    current_yr = date.today().year
    result=db.session.execute(db.select(Product))
    all_products=list(result.scalars())

    all_categories = list(db.session.execute(db.select(Category).join(Product).where(Category.id == Product.category_id)).scalars())

    result = db.session.execute(db.select(Brand).join(Product).where(Brand.id == Product.brand_id))
    all_brands = list(result.scalars())

    return render_template("admin.html",brands=all_brands,categories=all_categories,logged_in=current_user.is_authenticated,year=current_yr,products=all_products)


def require_login(func):
    @wraps(func)
    def fxn_decorator(*args,**kwargs):
        if not current_user.is_authenticated:
            flash("You must login first.")
            return redirect(url_for("login"))
        return func(*args,**kwargs)
    return fxn_decorator


@app.route("/home")
@require_login
def home():
    current_yr=date.today().year
    page=request.args.get("page",1,type=int)
    all_products=Product.query.filter(Product.stock>0).order_by(Product.id.desc()).paginate(page=page,per_page=8)

    data = db.session.execute(db.select(Brand))
    all_brands = list(data.scalars())

    all_categories=list(db.session.execute(db.select(Category)).scalars())

    return render_template("home.html",categories=all_categories,year=current_yr,logged_in=current_user.is_authenticated,products=all_products,brands=all_brands)


@app.route("/product/<int:id>")
@login_required
def product_details(id):
    current_yr = date.today().year

    get_product=db.session.execute(db.select(Product).where(Product.id==id)).scalar()

    data = db.session.execute(db.select(Brand))
    all_brands = list(data.scalars())

    all_categories = list(db.session.execute(db.select(Category)).scalars())

    return render_template("product_details.html",product=get_product,year=current_yr,brands=all_brands,categories=all_categories,logged_in=current_user.is_authenticated)


@app.route("/add-to-cart",methods=["GET","POST"])
def add2cart():
    id=request.form.get("product_id")
    quantity=request.form.get("quantity")
    color=request.form.get("color")

    product=db.session.execute(db.select(Product).where(Product.id==id)).scalar()

    item_dict={id:{"name":product.name,"price":product.price,"discount":product.discount,"quantity":quantity,"color":color,"image":product.image_1, "stock":product.stock,"colors":product.colors}}

    if request.method=="POST":
        if "shopping_cart" in session:  # if the cart exist, do this
            if id in session["shopping_cart"]:
                for key, value in session["shopping_cart"].items():
                    if key == id:
                        value["quantity"] = int(quantity) + int(value["quantity"])
                flash("The item is already in the cart.")
                return redirect(url_for("cart_items"))
            else:
                session["shopping_cart"] = MergedItemsDict(session["shopping_cart"],item_dict)
                flash(f"{item_dict[id]['name']} has been added to the cart.")
                return redirect(url_for("home"))
        else:
            # cart has been established for the 1st time and the first item will be added in the cart.
            session["shopping_cart"]=item_dict
            flash(f"{item_dict[id]['name']} has been added to the cart.")
            return redirect(url_for("home"))

    return False


@app.route("/cart_items")
@login_required
def cart_items():
    current_yr=date.today().year
    data = db.session.execute(db.select(Brand))
    all_brands = list(data.scalars())

    all_categories = list(db.session.execute(db.select(Category)).scalars())

    if len(session["shopping_cart"])==0:
        flash("Your cart is empty.")
        return redirect(url_for("home"))
    else:
        subtotal=0
        for key,value in session["shopping_cart"].items():
            rate = int(value["discount"]) / 100
            discount = (float(value["price"]) * int(value["quantity"])) * rate
            subtotal += (float(value["price"]) * int(value["quantity"])) - discount
            tax = "%.2f" % (0.05 * subtotal) # .05 means 5% tax
            total = "%.2f" % (1.05 * subtotal)
    return render_template("cart.html",logged_in=current_user.is_authenticated,brands=all_brands,categories=all_categories,year=current_yr,total=float(total),amount=subtotal,tax=float(tax))


@app.route("/update_cart/item-<int:id>",methods=["GET","POST"])
def update_cart(id):
    if request.method=="POST":
        quantity=request.form.get("quantity")
        color=request.form.get("color")

        for key,value in session["shopping_cart"].items():
            if int(key)==id:
                value["quantity"]=quantity
                value["color"]=color
                flash(f"Your item {value['name']} has been updated.")
                return redirect(url_for("cart_items"))
    return False


@app.route("/delete_item/item-<int:id>")
@login_required
def delete_item(id):
    session.modified=True # required in deleting dictionary data in session
    for key,value in session["shopping_cart"].items():
        if int(key)==id:
            session["shopping_cart"].pop(key,None)
            return redirect(url_for("cart_items"))
    return False


@app.route("/delete_cart")
def delete_cart():
    session.modified=True
    session.pop("shopping_cart",None)
    flash("Your cart is empty.")
    return redirect(url_for("home"))


@app.route("/search_results",methods=["GET","POST"])
def search_results():
    current_yr = date.today().year
    data = db.session.execute(db.select(Brand))
    all_brands = list(data.scalars())

    all_categories = list(db.session.execute(db.select(Category)).scalars())

    if request.method=="POST":
        keyword=request.form.get("keyword")
        results=db.session.execute(db.select(Product).where((Product.name.like('%'+str(keyword)+'%'))|(Product.description.like('%'+str(keyword)+'%'))))
        all_products=list(results.scalars())
        return render_template("results.html",brands=all_brands,categories=all_categories,year=current_yr,products=all_products,keyword=keyword,logged_in=current_user.is_authenticated)
    return False


@app.route("/get_brand/<int:id>")
@login_required
def get_brand(id):
    current_yr = date.today().year
    page=request.args.get("page",1,type=int)

    all_products=Product.query.filter(Product.brand_id==id).paginate(page=page,per_page=8)

    data = db.session.execute(db.select(Brand))
    all_brands = list(data.scalars())

    all_categories = list(db.session.execute(db.select(Category)).scalars())

    return render_template("home.html",categories=all_categories,year=current_yr,logged_in=current_user.is_authenticated,products=all_products,brands=all_brands)


@app.route("/get_category/<int:id>")
@login_required
def get_category(id):
    current_yr = date.today().year
    page=request.args.get("page",1,type=int)

    all_products=Product.query.filter(Product.category_id==id).paginate(page=page,per_page=8)

    data = db.session.execute(db.select(Brand))
    all_brands = list(data.scalars())

    all_categories = list(db.session.execute(db.select(Category)).scalars())

    return render_template("home.html",brands=all_brands,categories=all_categories,products=all_products,year=current_yr,logged_in=current_user.is_authenticated)


@app.route("/brands")
@login_required
def display_brands():
    current_yr = date.today().year
    result = db.session.execute(db.select(Brand))
    all_brands = list(result.scalars())
    return render_template("brands.html",logged_in=current_user.is_authenticated,year=current_yr,brands=all_brands)


@app.route("/categories")
@login_required
def display_categories():
    current_yr = date.today().year
    result = db.session.execute(db.select(Category))
    all_categories = list(result.scalars())
    return render_template("categories.html",logged_in=current_user.is_authenticated,year=current_yr,categories=all_categories)


@app.route("/register",methods=["GET","POST"])
def register():
    current_yr = date.today().year
    if request.method=="POST":
        fname=request.form.get("fname")
        lname = request.form.get("lname")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        pword = request.form.get("retype_pword")
        address=request.form.get("address")
        state = request.form.get("state")
        country = request.form.get("country")
        zipcode = request.form.get("zipcode")
        user_photo=request.files.get("photo")

        user=db.session.execute(db.select(User).where(User.email==email)).scalar()

        if user:
            flash("The email address already exist. Please login.")
            return redirect(url_for("login"))
        else:
            registered = db.session.execute(db.select(User).where(User.username == username)).scalar()

            if registered:
                flash("The username is already taken.")
                return redirect(url_for("register"))
            else:
                if password != pword:
                    flash("The password must match with the retyped password.")
                    return redirect(url_for("register"))
                else:
                    filename = secure_filename(user_photo.filename)
                    img_dir = "static/images/profile_pic/"

                    if filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".gif") or filename.endswith(".png"):
                        file_name = secrets.token_hex(10) + filename.split('.')[1]
                        file_path = os.path.join(img_dir, file_name)
                        user_photo.save(file_path)

                        hashed_and_salted_password = generate_password_hash(password, method="scrypt", salt_length=8)
                        new_user = User(firstname=fname, lastname=lname, username=username,email=email, password=hashed_and_salted_password,
                                        address=address,state=state,country=country,zipcode=zipcode,profile_pic=file_name)
                        db.session.add(new_user)
                        db.session.commit()
                        flash(f"Congrats, {fname.title()}! You are now registered.")
                        return redirect(url_for('login'))
                    else:
                        flash("Wrong file. Please upload an image.")
                        return redirect(url_for("register"))
    return render_template("register.html",year=current_yr)


@app.route("/logout")
def logout():
    logout_user()
    flash("You have logged out.")
    return redirect(url_for("login"))


def update_shoppingcart():
    for key,value in session["shopping_cart"].items():
        del value["image"]
        del value["colors"]


@app.route("/checkout")
@login_required
def make_order():
    update_shoppingcart()
    invoice=secrets.token_hex(5)
    new_order=Order(invoice=invoice,customer_id=current_user.id,items=session["shopping_cart"])
    db.session.add(new_order)

    for key, value in session["shopping_cart"].items():
        product = db.session.execute(db.select(Product).where(Product.name == value["name"])).scalar()
        product.stock = product.stock - int(value["quantity"])

    db.session.commit()
    session.modified=True
    session.pop("shopping_cart",None)
    return redirect(url_for("order_details",invoice=invoice))


@app.route("/order/invoice:<invoice>")
@login_required
def order_details(invoice):
    current_yr=date.today().year
    customer=db.session.execute(db.select(User).where(User.id==current_user.id)).scalar()
    customer_order=db.session.execute(db.select(Order).where((Order.customer_id==current_user.id) & (Order.invoice==invoice))).scalar()

    subtotal=0
    for key,value in customer_order.items.items():
        rate=int(value["discount"])/100
        discount=(float(value["price"]) * int(value["quantity"])) * rate
        subtotal+=(float(value["price"]) * int(value["quantity"])) - discount
        tax="%.2f" % (.05 * subtotal)
        total="%.2f" % (1.05 * subtotal)

    return render_template("order_details.html",year=current_yr,logged_in=current_user.is_authenticated,invoice=invoice,customer=customer,order=customer_order,amount=subtotal,tax=float(tax),total=total)


@app.route("/invoice_pdf/invoice:<invoice>",methods=["POST"])
@login_required
def order_details_as_pdf(invoice):
    if request.method=="POST":
        customer = db.session.execute(db.select(User).where(User.id == current_user.id)).scalar()
        customer_order = db.session.execute(db.select(Order).where((Order.customer_id == current_user.id) & (Order.invoice == invoice))).scalar()

        subtotal = 0
        for key, value in customer_order.items.items():
            rate = int(value["discount"]) / 100
            discount = (float(value["price"]) * int(value["quantity"])) * rate
            subtotal += (float(value["price"]) * int(value["quantity"])) - discount
            tax = "%.2f" % (.05 * subtotal)
            total = "%.2f" % (1.05 * subtotal)

        html_page=render_template("pdf.html",invoice=invoice,customer=customer,order=customer_order,amount=subtotal,tax=float(tax),total=float(total))
        # view as pdf
        config=pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
        pdf=pdfkit.from_string(html_page,configuration=config,options={"enable-local-file-access":""})
        response=make_response(pdf)
        response.headers["content-Type"]="application/pdf"
        response.headers["content-Disposition"]="inline; filename="+invoice+".pdf"
        # view as pdf
        return response
    return False


@app.route("/purchase",methods=["GET","POST"])
def get_payment():
    if request.method=="POST":
        invoice=request.form.get("invoice")
        amount=request.form.get("amount")

        customer=db.session.execute(db.select(User).where(User.id==current_user.id)).scalar()
        customer_order=db.session.execute(db.select(Order).where((Order.customer_id==current_user.id) & (Order.invoice==invoice))).scalar()

        customer_order.status = "paid"
        db.session.commit()

        customer = stripe.Customer.create(
            email=customer.email,
            source=request.form['stripeToken'],
        )

        charge = stripe.Charge.create(
            customer=customer.id,
            description='Custom t-shirt',
            amount=amount,
            currency='usd',
        )
        return redirect(url_for("thanx4shopping"))
    return False


@app.route("/thanx")
def thanx4shopping():
    current_yr=date.today().year
    return render_template("thanks.html",year=current_yr)


@app.route("/add_brand",methods=["GET","POST"])
def add_brand():
    current_yr = date.today().year
    form=BrandForm()
    if form.validate_on_submit():
        name=form.brandname.data
        brand=db.session.execute(db.select(Brand).where(Brand.name == name.title())).scalar()
        if brand:
            flash("The brand already exists in the database.")
            return render_template("add_brand.html",year=current_yr,form=form,is_exist=True,logged_in=current_user.is_authenticated)
        else:
            new_brand = Brand(name=name.title())
            db.session.add(new_brand)
            db.session.commit()
            flash(f"The brand {name.title()} has been added to the database.")
            return redirect(url_for("add_brand"))
    return render_template("add_brand.html",form=form,year=current_yr,logged_in=current_user.is_authenticated)


@app.route("/edit_brand/<int:brand_id>",methods=["GET","POST"])
def edit_brand(brand_id):
    current_yr=date.today().year
    requested_brand=db.session.execute(db.select(Brand).where(Brand.id==brand_id)).scalar()
    update_form = UpdateBrandForm(brand=requested_brand.name)

    if update_form.validate_on_submit():
        requested_brand.name=update_form.brand.data
        db.session.commit()
        flash("The brand name has been successfully updated.")
        return redirect(url_for('display_brands'))

    return render_template("edit_brand.html",year=current_yr,form=update_form,logged_in=current_user.is_authenticated)


@app.route("/delete_brand/<int:id>",methods=["POST"])
def delete_brand(id):
    if request.method=="POST":
        brand=db.session.execute(db.select(Brand).where(Brand.id==id)).scalar()
        db.session.delete(brand)
        db.session.commit()
        flash("The brand has been successfully deleted.")
        return redirect(url_for('display_brands'))
    return False


@app.route("/add_category",methods=["GET","POST"])
def add_category():
    current_yr = date.today().year
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.categoryname.data
        category = db.session.execute(db.select(Category).where(Category.name == name.lower())).scalar()
        if category:
            flash("The category already exists in the database.")
            return render_template("add_category.html", form=form, is_exist=True,logged_in=current_user.is_authenticated)
        else:
            new_category = Category(name=name)
            db.session.add(new_category)
            db.session.commit()
            flash(f"The {name.lower()} category has been added to the database.")
            return redirect(url_for("add_category"))
    return render_template("add_category.html",form=form,year=current_yr,logged_in=current_user.is_authenticated)


@app.route("/edit_category/<int:category_id>",methods=["GET","POST"])
def edit_category(category_id):
    current_yr=date.today().year
    requested_category=db.session.execute(db.select(Category).where(Category.id==category_id)).scalar()
    update_form = UpdateCategoryForm(category=requested_category.name)

    if update_form.validate_on_submit():
        requested_category.name=update_form.category.data
        db.session.commit()
        flash("The category name has been successfully updated.")
        return redirect(url_for('display_categories'))

    return render_template("edit_category.html",year=current_yr,form=update_form,logged_in=current_user.is_authenticated)


@app.route("/delete_category/<int:id>",methods=["POST"])
def delete_category(id):
    if request.method=="POST":
        db.session.delete(db.session.execute(db.select(Category).where(Category.id==id)).scalar())
        db.session.commit()
        flash("The category has been deleted.")
        return redirect(url_for('display_categories'))


@app.route("/edit_product/<int:product_id>",methods=["GET","POST"])
def edit_product(product_id):
    current_yr = date.today().year

    result = db.session.execute(db.select(Brand).order_by(Brand.name))
    all_brands = list(result.scalars())

    data = db.session.execute(db.select(Category).order_by(Category.name))
    all_categories = list(data.scalars())

    requested_product=db.session.execute(db.select(Product).where(Product.id==product_id)).scalar()

    img_dir="static/images/products"

    if request.method=="POST":
        requested_product.name=request.form.get("name")
        requested_product.price = request.form.get("price")
        requested_product.discount=request.form.get("discount")
        requested_product.stock=request.form.get("stock")
        requested_product.description=request.form.get("description")
        requested_product.colors=request.form.get("colors")
        requested_product.brand_id=request.form.get("brand")
        requested_product.category_id = request.form.get("category")

        img1_file=request.files.get("image_1")
        img2_file=request.files.get("image_2")
        img3_file=request.files.get("image_3")

        if img1_file:
            img1 = secure_filename(img1_file.filename)

            if img1.endswith(".jpg") or img1.endswith(".gif") or img1.endswith(".png") or img1.endswith(".jpeg"):
                os.unlink(os.path.join(img_dir, requested_product.image_1))
                img_1=secrets.token_hex(10) + '.' + img1.split('.')[1]
                img1_filepath = os.path.join(img_dir, img_1)
                img1_file.save(img1_filepath)
                requested_product.image_1 = img_1
            else:
                flash("Wrong file. Please upload an image.")
                return render_template("edit_product.html", year=current_yr, product=requested_product,
                                           brands=all_brands, categories=all_categories, is_error=True,logged_in=current_user.is_authenticated)

        if img2_file:
            img2 = secure_filename(img2_file.filename)

            if img2.endswith(".jpg") or img2.endswith(".gif") or img2.endswith(".png") or img2.endswith(".jpeg"):
                os.unlink(os.path.join(img_dir, requested_product.image_2))
                img_2 = secrets.token_hex(10) + '.' + img2.split('.')[1]
                img2_filepath = os.path.join(img_dir, img_2)
                img2_file.save(img2_filepath)
                requested_product.image_2 = img_2
            else:
                flash("Wrong file. Please upload an image.")
                return render_template("edit_product.html", year=current_yr, product=requested_product,
                                           brands=all_brands, categories=all_categories, is_error=True,logged_in=current_user.is_authenticated)

        if img3_file:
            img3 = secure_filename(img3_file.filename)

            if img3.endswith(".jpg") or img3.endswith(".gif") or img3.endswith(".png") or img3.endswith(".jpeg"):
                os.unlink(os.path.join(img_dir, requested_product.image_3))
                img_3 = secrets.token_hex(10) + '.' + img3.split('.')[1]
                img3_filepath = os.path.join(img_dir, img_3)
                img3_file.save(img3_filepath)
                requested_product.image_3 = img_3
            else:
                flash("Wrong file. Please upload an image.")
                return render_template("edit_product.html", year=current_yr, product=requested_product,
                                           brands=all_brands, categories=all_categories, is_error=True,logged_in=current_user.is_authenticated)

        db.session.commit()
        flash("The product has been successfully updated.")
        return redirect(url_for('admin'))

    return render_template("edit_product.html",year=current_yr,product=requested_product,brands=all_brands,categories=all_categories,logged_in=current_user.is_authenticated)


@app.route("/add_product",methods=["GET","POST"])
def add_product():
    current_yr = date.today().year

    result=db.session.execute(db.select(Brand).order_by(Brand.name))
    all_brands=list(result.scalars())

    data = db.session.execute(db.select(Category).order_by(Category.name))
    all_categories = list(data.scalars())

    img_dir="static/images/products"

    if request.method=="POST":
        name=request.form.get("name")
        price = request.form.get("price")
        discount = request.form.get("discount")
        stock = request.form.get("stock")
        desc = request.form.get("description")
        colors = request.form.get("colors")
        brand_id = request.form.get("brand")
        category_id = request.form.get("category")
        file1=request.files.get("image_1")
        file2 = request.files.get("image_2")
        file3 = request.files.get("image_3")

        img1=secure_filename(file1.filename)
        img2 = secure_filename(file2.filename)
        img3 = secure_filename(file3.filename)

        if img1.endswith(".jpg") or img1.endswith(".gif") or img1.endswith(".jpeg") or img1.endswith(".png"):
            img_1 = secrets.token_hex(10) + '.' + img1.split('.')[1]
            file1.save(os.path.join(img_dir, img_1))
        else:
            flash("Wrong file. Pls upload an image.")
            return render_template("add_product.html", year=current_yr, brands=all_brands, categories=all_categories,
                                   is_error=True, logged_in=current_user.is_authenticated)

        if img2.endswith(".jpg") or img2.endswith(".gif") or img2.endswith(".jpeg") or img2.endswith(".png"):
            img_2 = secrets.token_hex(10) + '.' + img2.split('.')[1]
            file2.save(os.path.join(img_dir, img_2))
        else:
            flash("Wrong file. Pls upload an image.")
            return render_template("add_product.html", year=current_yr, brands=all_brands, categories=all_categories,
                                   is_error=True, logged_in=current_user.is_authenticated)

        if img3.endswith(".jpg") or img3.endswith(".gif") or img3.endswith(".jpeg") or img3.endswith(".png"):
            img_3 = secrets.token_hex(10) + '.' + img3.split('.')[1]
            file3.save(os.path.join(img_dir, img_3))
        else:
            flash("Wrong file. Pls upload an image.")
            return render_template("add_product.html", year=current_yr, brands=all_brands, categories=all_categories,
                                   is_error=True, logged_in=current_user.is_authenticated)

        new_product=Product(name=name,price=price,discount=discount,stock=stock,description=desc,
                colors=colors,brand_id=brand_id,category_id=category_id,image_1=img_1,image_2=img_2,image_3=img_3)
        db.session.add(new_product)
        db.session.commit()
        flash("The product has been added to the database.")
        return redirect(url_for("admin"))

    return render_template("add_product.html",year=current_yr,brands=all_brands,categories=all_categories,logged_in=current_user.is_authenticated)


@app.route("/delete_product/<int:id>",methods=["POST"])
def delete_product(id):
    img_dir = "static/images/products"
    if request.method=="POST":
        product=db.session.execute(db.select(Product).where(Product.id==id)).scalar()
        os.unlink(os.path.join(img_dir,product.image_1))
        os.unlink(os.path.join(img_dir, product.image_2))
        os.unlink(os.path.join(img_dir, product.image_3))
        db.session.delete(product)
        db.session.commit()
        return redirect(url_for('admin'))
    return False


if __name__=="__main__":
    app.run(debug=False)