import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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

    #initialize market value and query portfolio
    marketvalue = 0
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id=?", session["user_id"])

    # update portfolio when page is visited
    for stock in portfolio:
        symbol = stock["stock"]
        shares = stock["shares"]
        currentprice = lookup(symbol)["price"]
        total = shares * currentprice
        marketvalue += total
        db.execute("UPDATE portfolio SET current_price = ?, total = ? WHERE stock=?", currentprice, total, symbol)

    # query users for cash
    cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # query (updated) portfolio
    rows = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])

    if request.method == "GET":
        return render_template("index.html", cash=cash[0]["cash"], rows=rows, marketvalue=marketvalue)

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():

    rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    if request.method == "GET":
        return render_template("account.html", cash=rows[0]["cash"])

    if request.method == "POST":
        if not request.form.get("add").isnumeric():
            return apology("Please enter valid amount")
        elif request.form.get("add") == None:
            return apology("Please enter valid amount")
        elif request.form.get("add") == '0':
            return apology("Please enter valid amount")
        funds = int(request.form.get("add"))
        if funds > 10000:
            return apology("Cannot add more than $10000", 400)
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", funds, session["user_id"])
        db.execute("INSERT INTO transactions (user_id, type, price, date) VALUES (?, ?, ?, datetime('now'))", session["user_id"], "deposit", funds)

    return redirect("/")
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # query users to display cash
    rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # display cash with get request
    if request.method == "GET":
        return render_template("buy.html", cash=rows[0]["cash"])

    elif request.method == "POST":

        # check validity of symbol and shares
        symbol = lookup(request.form.get("symbol"))
        shares = request.form.get("shares")
        if not shares.isnumeric():
            return apology("Invalid number of shares", 400)
        elif symbol is None:
            return apology("Invalid Ticker Symbol", 400)

        else:
            # get symbol string from symbol dict
            symbol = symbol["symbol"]

            # query portfolio for symbol typed in
            query = db.execute("SELECT * FROM portfolio WHERE stock = ? AND user_id = ?", symbol, session["user_id"])

            # get the current price of stock
            currentprice = lookup(symbol)["price"]

            # if stock is already owned by user, get shares
            if len(query) > 0:
                currentshares = int(query[0]["shares"])

            # if stock not owned, initialize shares to 0
            else:
                currentshares = 0

            # given what user entered, calculate the total number of shares, and total cost of transaction
            sharesordered = int(request.form.get("shares"))
            totalshares = currentshares + sharesordered
            total = int(sharesordered) * float(currentprice)

            # check if enough money
            if total > rows[0]["cash"]:
                return apology("Not Enough Money to Buy")

            # subtract cost of transaction from cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?", rows[0]["cash"]-total, session["user_id"])

            # record buy in transactions
            db.execute("INSERT INTO transactions (user_id, type, stock, shares, price, date) VALUES (?, ?, ?, ?, ?, datetime('now'))", session["user_id"], "buy", symbol, sharesordered, currentprice)

            # if stock owned by user, increase shares and total, otherwise, insert into portfolio
            if len(query) > 0:
                db.execute("UPDATE portfolio SET shares = ?, current_price = ?, total = total + ? WHERE user_id = ? AND stock = ?", totalshares, currentprice, total, session["user_id"], symbol)
            else:
                db.execute("INSERT INTO portfolio (user_id, stock, shares, current_price, total) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbol, request.form.get("shares"), currentprice, int(request.form.get("shares"))*(currentprice))

        return redirect("/")

@app.route("/history")
@login_required
def history():
    if request.method == "GET":
        histories = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC", session["user_id"])
        return render_template("history.html", histories=histories)

@app.route("/login", methods=["GET", "POST"])
def login():

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

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    elif request.method == "POST":
        rows = lookup(request.form.get("symbol"))
        if not rows:
            return apology("Invalid Symbol")
        return render_template("quoted.html", stock=rows)

@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    if request.method == "POST":
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) >= 1:
            return apology("username already taken", 400)

        elif not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (?,?)", request.form.get("username"), generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8))

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    # initialize and gather a list of stocks that user owns
    portfolio = db.execute("SELECT stock, shares, current_price, total FROM portfolio WHERE user_id=?", session["user_id"])
    listofstocks = []
    for i in range(len(portfolio)):
        listofstocks.append(portfolio[i]["stock"])

    if request.method == "GET":
        return render_template("sell.html", portfolio=portfolio)

    elif request.method == "POST":
        cash = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
        cash = cash[0]["cash"]
        stock = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        priceofshare = lookup(stock)["price"]
        currentshares = int(db.execute("SELECT shares FROM portfolio WHERE stock = ? AND user_id = ?", stock, session["user_id"])[0]["shares"])
        if not request.form.get("symbol"):
            return apology("Please select stock you wish to sell")

        elif not request.form.get("shares"):
            return apology("Invalid number of shares")

        elif int(request.form.get("shares")) <= 0:
            return apology("Invalid number of shares")

        elif request.form.get("symbol") not in listofstocks:
            return apology("You do not own this stock!")

        elif shares > currentshares:
            return apology("Please select valid number of shares")

        else:

            newshares = currentshares - shares
            newtotal = newshares * priceofshare

            db.execute("INSERT INTO transactions (user_id, type, stock, shares, price, date) VALUES (?, ?, ?, ?, ?, datetime('now'))", session["user_id"], "sell", request.form.get("symbol"), request.form.get("shares"), priceofshare)
            db.execute("UPDATE users SET cash= ? WHERE id=?", cash + (int(request.form.get("shares")) * lookup(request.form.get("symbol"))["price"]), session["user_id"])
            if currentshares == shares:
                db.execute("DELETE FROM portfolio WHERE user_id = ? AND stock = ?", session["user_id"], stock)
            else:
                db.execute("UPDATE portfolio SET shares=?, total = ? WHERE user_id=? AND stock=?", newshares, newtotal, session["user_id"], stock)
            portfolio = db.execute("SELECT stock, shares, current_price, total FROM portfolio WHERE user_id=?", session["user_id"])
            return redirect("/")