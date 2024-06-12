from flask_wtf import FlaskForm
from flask_wtf.file import FileRequired,FileAllowed
from wtforms import StringField,PasswordField,SubmitField,IntegerField,DecimalField,FileField,TextAreaField
from wtforms.validators import DataRequired,Email


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class BrandForm(FlaskForm):
    brandname = StringField("Brand Name", validators=[DataRequired()])
    submit = SubmitField("Add Brand")


class UpdateBrandForm(FlaskForm):
    brand = StringField("Brand Name", validators=[DataRequired()])
    submit = SubmitField("Update Brand")


class CategoryForm(FlaskForm):
    categoryname = StringField("Category Name", validators=[DataRequired()])
    submit = SubmitField("Add Category")


class UpdateCategoryForm(FlaskForm):
    category = StringField("Category Name", validators=[DataRequired()])
    submit = SubmitField("Update Category")


class ProductForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()], render_kw={"placeholder": "Add product name"})
    price = DecimalField("Price", validators=[DataRequired()], render_kw={"placeholder": "Add product price"})
    discount = IntegerField("Discount", default=0)
    stock = IntegerField("Stock", validators=[DataRequired()], render_kw={"placeholder": "No. of product stock"})
    description = TextAreaField("Description", validators=[DataRequired()],
                                render_kw={"placeholder": "Add product details"})
    colors = TextAreaField("Colors", validators=[DataRequired()], render_kw={"placeholder": "Add product colors"})

    image_1 = FileField("Image 1", validators=[FileRequired(), FileAllowed(["jpg", "gif", "png", "jpeg"])])
    image_2 = FileField("Image 2", validators=[FileRequired(), FileAllowed(["jpg", "gif", "png", "jpeg"])])
    image_3 = FileField("Image 3", validators=[FileRequired(), FileAllowed(["jpg", "gif", "png", "jpeg"])])
    submit = SubmitField("Add")