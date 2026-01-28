import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import time
from zoneinfo import ZoneInfo

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # select user's stock portfolio and cash total
    rows = db.execute("SELECT * FROM portofolio WHERE user_id = :id", id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    cash = cash[0]['cash']

    # this will be total value of all stock holdings and cash

    return render_template("index.html", cash=usd(cash), rows=rows)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        if not symbol:
            return apology("must provide stock symbol")
        elif not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("must provide positive number of shares", 400)

        quote = lookup(symbol)
        if quote == None:
            return apology("wrong stock symbol")

        user_id = session["user_id"]

        price = quote["price"]
        total_cost = int(shares) * price

        balance = db.execute("SELECT cash FROM users where id = ?", user_id)
        balance = balance[0]["cash"]
        remainder = balance - total_cost

        shares = int(shares)

        if balance < total_cost:
            return apology("not enough cash")

        row = db.execute("SELECT * FROM portofolio WHERE user_id = :id AND symbol = :symbol",
                         id=session["user_id"], symbol=symbol)

        if len(row) == 0:
            db.execute("INSERT INTO portofolio (user_id, symbol,shares,price,total) VALUES (:id, :symbol,:shares,:price,:total_cost)",
                       id=user_id, symbol=symbol, shares=0, price=usd(price), total_cost =0)

        oldshares = db.execute("SELECT shares FROM portofolio WHERE user_id = :id AND symbol = :symbol",
                               id=session["user_id"], symbol=symbol)
        oldshares = oldshares[0]["shares"]

        # add purchased shares to previous share number

        db.execute("UPDATE portofolio SET shares = :newshares WHERE user_id = :id AND symbol = :symbol",
                   newshares=oldshares + shares, id=session["user_id"], symbol=symbol)

        newshares = oldshares + shares

        db.execute("UPDATE portofolio SET total = :total WHERE user_id = :id AND symbol = :symbol",
                   total=newshares * price, id=session["user_id"], symbol=symbol)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder, user_id)

        date = datetime.now(tz=ZoneInfo("Asia/Jakarta"))

        db.execute("INSERT INTO transactions (user_id,symbol,shares,current_price,total_price,balance,date,method) VALUES(?,?,?,?,?,?,?,?)",
                   user_id, quote["symbol"], shares, usd(quote["price"]), usd(total_cost), usd(balance), date, 'Buy')

        flash(f"bought {shares} shares of {symbol} for {usd(total_cost)}")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id = :userid ORDER BY date DESC", userid=session["user_id"])

    # return history template
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    symbol = request.form.get("symbol")

    if request.method == "POST":

        if not symbol:
            return apology("must provide stock symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("wrong stock symbol")

        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=usd(stock["price"]))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    name = request.form.get("username")
    password = request.form.get("password")
    password_confirm = request.form.get("confirmation")
    rows = db.execute("SELECT * FROM users WHERE username = ?", name)

    if request.method == "POST":
        # Ensure username was submitted
        if not name:
            return apology("must provide username")
        # Ensure password was submitted
        elif not password:
            return apology("must provide password")
        elif not password_confirm:
            return apology("must provide confirmation")
        elif password != password_confirm:
            return apology("password not match")
        elif len(rows) != 0:
            return apology("invalid username")
        else:
            db.execute("INSERT INTO users (username,hash) VALUES(?,?)", name, generate_password_hash(password))
            rows = db.execute("SELECT * FROM users WHERE username = ?", name)
            session["user_id"] = rows[0]["id"]
            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    all_stocks = db.execute("SELECT symbol FROM portofolio WHERE user_id = (?)", user_id)
    user_symbols = []
    for all_symbol in all_stocks:
        user_symbols.append(all_symbol["symbol"].upper())
    if request.method == "POST":
        if len(all_stocks) == 0:
            return apology("no symbol to sell")

        symbol = request.form.get("symbol")
        if symbol not in user_symbols or symbol == None:
            return apology("the symbol is not in the list")

        shares = request.form.get("shares")
        select_user_shares = db.execute("SELECT shares FROM portofolio WHERE user_id = (?) AND symbol = (?)", user_id, symbol)
        user_shares = select_user_shares[0]["shares"]

        if int(shares) > user_shares:
            return apology("invalid shares amount")
        if shares == None or not shares.isdigit():
            return apology("invalid shares amount")

        price = lookup(symbol.upper())["price"]
        symbol = lookup(symbol.upper())["symbol"]

        total_cost = float(shares) * price

        balance = db.execute("SELECT cash FROM users where id = ?", user_id)
        balance = balance[0]["cash"]
        cash = balance + total_cost

        # add purchased shares to previous share number
        newshares = user_shares - int(shares)

        db.execute("UPDATE portofolio SET shares = :newshares WHERE user_id = :id AND symbol = :symbol",
                   newshares=newshares, id=session["user_id"], symbol=symbol)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        # otherwise delete stock row because no shares remain
        if newshares <= 0:
            db.execute("DELETE FROM portofolio WHERE symbol = :symbol AND user_id = :id",
                       symbol=symbol, id=session["user_id"])

        date = datetime.now(tz=ZoneInfo("Asia/Jakarta"))
        # update history table
        db.execute("INSERT INTO transactions (user_id,symbol,shares,current_price,total_price,balance,date,method) VALUES(?,?,?,?,?,?,?,?)",
                   user_id, symbol, shares, usd(price), usd(total_cost), usd(balance), date, 'Sell')

        flash(f"sold {shares} shares of {symbol} for {usd(total_cost)}")
        # redirect to index page
        return redirect("/")

    else:
        # get the user's current stocks
        portfolio = db.execute("SELECT * FROM portofolio WHERE user_id = :id",
                               id=session["user_id"])

        # render sell.html form, passing in current stocks
        return render_template("sell.html", portfolio=portfolio)
