import string
import os
from pathlib import Path
NULL = None
from urllib.parse import urlparse


from flask import Flask, render_template, request, redirect, session, flash,url_for,jsonify
from flask_socketio import join_room, leave_room, send,SocketIO
from string import ascii_uppercase
from datetime import date
import random
import secrets
import sqlite3
import hashlib
import urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or __import__('secrets').token_hex(32)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
DB_PATH = Path(__file__).resolve().parent / 'scripts' / 'nittanyauction.db'
socketio = SocketIO(app)



############################################################
#-------------------Helper Functions-----------------------#
############################################################


#-----------------------------------------------------#
#initiating database
#with open('scripts/populationScript.py') as popFile:
    #exec(popFile.read())
#-----------------------------------------------------#

#connect to the sqlite database and returns connection
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout= 60)
    conn.row_factory = sqlite3.Row#lets us access columns by name
    return conn

#-----------------------------------------------------#

#determine provided users role by checking helpdesk,seller,and bidder table
def get_role(email):
    conn = get_db()
    #check which table users email is in to determine their role
    if conn.execute('SELECT * FROM HelpDesk WHERE email_pk = ?', (email,)).fetchone():
        conn.close()
        return 'HelpDesk'
    if conn.execute('SELECT * FROM Sellers WHERE email_fk = ?', (email,)).fetchone():
        conn.close()
        return 'Seller'
    if conn.execute('SELECT * FROM Bidders WHERE email_fk = ?',(email,)).fetchone():
        conn.close()
        return 'Bidder'
    conn.close()
    return None
#-----------------------------------------------------#

#function to add new users to the users table
def add_users(email, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    conn.execute('INSERT INTO Users VALUES (?, ?)', (email, hashed_pw))
    conn.commit()
    conn.close()
    return None
#-----------------------------------------------------#


#helper function to get all products from a category
def get_products_by_category(conn, category_name):
    return conn.execute("""
        SELECT
            al.seller_email_fk AS seller_email, 
            al.listing_ID AS listing_id,
            al.category_fk as category,
            al.auction_title,
            al.product_name,
            al.product_description,
            al.quantity,
            al.reserve_price,                               --min price seller will accept
            al.max_bids,                                    --max # of bids allowed
            al.status,
            COALESCE(MAX(b.bid_price), 0) AS current_bid,   --highest bid placed, 0 if none
            al.max_bids - COUNT(b.Bid_ID) AS remaining_bids, --# of bids still allowed
            CASE WHEN p.promotion_id IS NOT NULL THEN 1 ELSE 0 END AS is_promoted
        FROM Auction_Listings al
        LEFT JOIN Bids b                                    --keeps listings with no bids
            ON al.seller_email_fk = b.seller_email_fk       
            AND al.listing_ID = b.listing_ID_fk             --matches seller & listing
        LEFT JOIN Promotions p
            ON al.seller_email_fk = p.seller_email_fk
            AND al.listing_ID = p.listing_id_fk
        WHERE al.category_fk = ?                            --return active listings only
            AND al.status = 1
        GROUP BY                                            --collapses rows to highest bid row
            al.seller_email_fk,
            al.listing_ID,
            al.category_fk,
            al.auction_title,
            al.product_name,
            al.product_description,
            al.quantity,
            al.reserve_price,
            al.max_bids,
            al.status,
            p.promotion_id
        ORDER BY is_promoted DESC, al.auction_title         --sort results by promotion first then a-z by title
                """,(category_name,)).fetchall()

#gets  details for a single auction listing identified by seller email
#returns one row or none if no matching listing found
def get_listing_detail(conn, seller_email, listing_id):
    return conn.execute("""
    SELECT
        al.seller_email_fk AS seller_email,
        al.listing_ID AS listing_id,
        al.category_fk AS category,
        al.auction_title,
        al.product_name,
        al.product_description,
        al.quantity,
        al.reserve_price,                                   --min price seller accepts
        al.max_bids,                                        --# of bids allowed on auction
        al.status,
        COALESCE(MAX(b.bid_price), 0) AS current_bid,
        al.max_bids - COUNT(b.Bid_ID) AS remaining_bids
    FROM Auction_Listings al 
    LEFT JOIN Bids b 
        ON al.seller_email_fk = b.seller_email_fk
        AND al.listing_ID = b.listing_ID_fk
    WHERE al.seller_email_fk = ?                            --filter to specific seller
        AND al.listing_ID = ?
    GROUP BY
        al.seller_email_fk, 
        al.listing_ID, 
        al.category_fk, 
        al.auction_title, 
        al.product_name, 
        al.product_description, 
        al.quantity, 
        al.reserve_price, 
        al.max_bids, 
        al.status
        """, (seller_email, listing_id)).fetchone()         #Only expect 1 listing to return

#search active listing by keyword, min price, and maaxprice
#query is dynamic
#returns all matching listings sorted a-z
def search_products(conn, keyword='', min_price=None, max_price=None):
    query = """
        SELECT
            al.seller_email_fk AS seller_email,
            al.listing_ID AS listing_id,
            al.category_fk AS category,
            al.auction_title,
            al.product_name,
            al.product_description,
            al.reserve_price,                               --min price seller accepts
            al.status,
            COALESCE(MAX(b.bid_price), 0) AS current_bid    --highst placed bid
        FROM Auction_Listings al
        LEFT JOIN Bids b 
            ON al.seller_email_fk = b.seller_email_fk
            AND al.listing_ID = b.listing_ID_fk
        WHERE al.status = 1
    """
    params = [] #holds values to inject into the query

    #search across relevan texts fields if keyword given
    if keyword:
        query +="""
        AND(
            al.auction_title LIKE ?
            OR al.product_name LIKE ?
            OR al.product_description LIKE ?
            OR al.category_fk LIKE ?
            OR al.seller_email_fk LIKE ?
            )
        """
        like_term = f"%{keyword}%" #matches anything before or after the keyword
        params.extend([like_term, like_term, like_term, like_term, like_term])

    if min_price:
        query += " AND al.reserve_price >= ?" #allows only listings above or equal min price
        params.append(min_price)

    if max_price:
        query += " AND al.reserve_price <= ?"#allows only lisings below or equal to max price
        params.append(max_price)


    #group by bcause we used MAX() on bid_price
    #order by sorts listings a-z by title
    query += """
        GROUP BY
            al.seller_email_fk,
            al.listing_ID,
            al.category_fk,
            al.auction_title,
            al.product_name,
            al.product_description,
            al.reserve_price,
            al.status
        ORDER BY al.auction_title
    """
    return conn.execute(query, params).fetchall()



#gets all leaf categories, excludes any category that is a parent
def get_leaf_categories(conn):
    return conn.execute("""
            SELECT category_name FROM Categories
            WHERE category_name NOT IN(
                SELECT DISTINCT parent_category_fk FROM Categories
                WHERE parent_category_fk IS NOT NULL)
                ORDER BY category_name
    """).fetchall()


#function to check whether the user already exists
def duplicate_email(email):
    conn = sqlite3.connect(DB_PATH)
    dupe_email = conn.execute('SELECT email_pk FROM Users WHERE email_pk = ?', (email,)).fetchone()
    conn.commit()
    conn.close()
    if dupe_email:
        return True
    else:
        return False
#-----------------------------------------------------#
#function to make a new address ID using the secrets library
def get_address_id(zipcode,stnum,stname):
    address_id = secrets.token_hex(16)
    conn = get_db()
    existing_id = conn.execute('SELECT * FROM Address A WHERE A.address_ID_pk = ? ', (address_id,)).fetchone()
    conn.commit()
    if existing_id:
        conn.close()
        return NULL
    else:
        conn.execute('INSERT INTO Address VALUES (?,?,?,?)', (address_id,zipcode ,stnum, stname))
        conn.commit()
        conn.close()
        return address_id
    # -----------------------------------------------------#


##########################################################################
#----------------------------ROUTES--------------------------------------#
##########################################################################

@app.route('/') #root route, redirects to login page
def home():
    return redirect('/login')


#handles displaying login form and processing login submission
#validates credentials and redirects to users specific role home page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
            #take user email/password input
            email = request.form['email']
            password = request.form['password']
            #hash the password to compare with stored hash
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()

            #connect to DB and check if a user exits with the email & password
            conn = get_db()
            user = conn.execute(
                    'SELECT * FROM Users WHERE email_pk = ? AND password =?',
                (email, hashed_pw)).fetchone()
            conn.close()

            if user:
                #login is successful, we now redirect to the correct role
                role = get_role(email)
                session['email'] = user['email_pk']
                session['role'] = role

                #decides which dashboard to redirect to based on role
                if role == 'Bidder':
                    return redirect('/bidder')
                elif role == 'Seller':
                    return redirect('/seller')
                elif role == 'HelpDesk':
                    return redirect('/helpdesk')
            else:
                #login failed
                return render_template('login.html', error='Invalid email/password')

    return render_template('login.html')


#Role specific dashboard routes
@app.route('/bidder')
def bidder():
    if 'email' not in session:
        return redirect('/login')

    email = session['email']
    conn = get_db()

    #get all the notifications for this user from the db and pass them with page rendering.
    notifications = conn.execute("""
                        SELECT notification_ID, message
                        FROM Notifications
                        WHERE user_email_fk = ? and is_read = 0
        """,(email,)).fetchall()
    conn.close()

    return render_template('bidder.html', email=session['email'],notifications=notifications)

@app.route('/seller')
def seller():
    if 'email' not in session:
        return redirect('/login')


    conn= get_db()
    seller_email = session['email']

    #get all listings of the current user
    active = conn.execute("""
        SELECT * FROM Auction_Listings
        WHERE seller_email_fk = ? AND status = 1
    """, (seller_email,)).fetchall()

    inactive = conn.execute("""
    SELECT * FROM Auction_Listings
        WHERE seller_email_fk = ? AND status = 0
    """, (seller_email,)).fetchall()

    sold = conn.execute("""
    SELECT * FROM Auction_Listings
    WHERE seller_email_fk = ? AND status = 2
    """, (seller_email,)).fetchall()

    conn.close()
    return render_template('seller.html', email=seller_email,
                           active=active, inactive=inactive, sold=sold)


@app.route('/logout')
def logout():
    session.clear()#wipes users session to log them out
    return redirect('/login')

@app.route('/categories')#all categories
@app.route('/categories/<category_name>')#specific category in url
def categories(category_name='Root'):#defaults to category root if no cat_name is given
    if 'email' not in session: #check if user is logged in
        return redirect('login')
    conn = get_db()

    subcategories = conn.execute( #find all children of current category
        'SELECT category_name FROM Categories WHERE parent_category_fk = ?',(category_name,)
    ).fetchall()

    #get parent for going back to parent category
    parent = conn.execute('SELECT parent_category_fk FROM Categories WHERE category_name = ?', (category_name,)).fetchone()

    #only fetch products if were in a real category(not root)
    products=[]
    promoted=[]

    if category_name == 'Root':
        promoted=conn.execute("""
            SELECT
                al.seller_email_fk AS seller_email,
                al.listing_ID AS listing_id,
                al.category_fk AS category,
                al.auction_title,
                al.product_name,
                al.reserve_price,
                COALESCE(MAX(b.bid_price), 0) AS current_bid,
                p.promoted_at
            FROM Promotions p
            JOIN Auction_Listings al
                ON p.seller_email_fk = al.seller_email_fk
                AND p.listing_id_fk = al.listing_ID
            LEFT JOIN Bids b
                ON al.seller_email_fk = b.seller_email_fk
                AND al.listing_ID = b.listing_ID_fk
            WHERE al.status = 1
            GROUP BY al.seller_email_fk, al.listing_ID, al.category_fk, al.auction_title, al.product_name, al.reserve_price, p.promoted_at
            ORDER BY p.promoted_at DESC
            """).fetchall()


    else:
        products = get_products_by_category(conn, category_name)
    conn.close()

    #get parents name if it exists so the back button can actually traverse backwards
    parent_category = parent['parent_category_fk'] if parent else None
    #changes display name to 'ALL' instead of 'Root', else it shows the cat name if its not root
    display_name = 'ALL' if category_name == 'Root' else category_name
    return render_template('categories.html',
                           category_name=category_name,         #used for building links in the html
                           display_name=display_name,           #page heading
                           subcategories=subcategories,         #list of child categoris
                           parent_category=parent_category,     #used for back button
                           products=products,                    #listings in the category
                           promoted=promoted
                           )

#accepts keyword, min_price, max_price to search databse for listing
@app.route('/search')
def search():
    if 'email' not in session:      #check user is logged in
        return redirect('/login')

    #request.args reads get parameters from URL
    #default to empty string if nothing provided, remove whitespaces w/ strip
    keyword = request.args.get('keyword','').strip()
    min_price = request.args.get('min_price','').strip()
    max_price = request.args.get('max_price','').strip()

    conn = get_db()
    results = search_products(conn, keyword, min_price, max_price)
    conn.close()

    #pass results and search parameters back to .html
    return render_template(
        'search_results.html',
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        results=results
    )


##################################################################################################################################################
#-------------------Listing Functions---------------------#######################################################################################
##################################################################################################################################################

#displays full info of an auction listing
@app.route('/listing/<seller_email>/<int:listing_id>')
def listing_detail(seller_email, listing_id):
    if 'email' not in session:              #check user is logged in
        return redirect('/login')

    conn = get_db()
    listing = get_listing_detail(conn, seller_email, listing_id)        #fetch the specific listing from DB

    if listing is None:
        conn.close()
        return "Listing Not Found", 404         #no listing found, 404

    in_watchlist = conn.execute("""
        SELECT * FROM Watchlist
        WHERE bidder_email_fk = ? AND seller_email_fk = ? AND listing_ID_fk = ?
    """, (session['email'], seller_email, listing_id)).fetchone()

    conn.close()
    return render_template('listing_detail.html', listing=listing, in_watchlist=in_watchlist)       #pass listing data to .html

#Allows seller to create a new auction listing
@app.route('/seller/create', methods=['GET', 'POST'])
def create_listing():
    if 'email' not in session:
        return redirect('/login')

    conn=get_db()
    categories = get_leaf_categories(conn)
    if request.method == 'POST':
        #get form fields
        auction_title = request.form['auction_title']
        product_name = request.form['product_name']
        product_description = request.form['product_description']
        category_fk = request.form['category_fk']
        quantity = request.form['quantity']
        reserve_price = request.form['reserve_price']
        max_bids = request.form['max_bids']
        seller_email = session['email']

        #generate listing id, add 1 to highest listing id
        next_id = conn.execute("""
                SELECT COALESCE(MAX(listing_ID), 0) + 1
                FROM Auction_Listings
                WHERE seller_email_fk = ?
        """, (seller_email,)).fetchone()[0]

        #insert new listing into database
        conn.execute("""
            INSERT INTO Auction_Listings
                (seller_email_fk, listing_ID, category_fk, auction_title, product_name, product_description, quantity, reserve_price, max_bids, status)
                VALUES(?,?,?,?,?,?,?,?,?,1)
        """,(seller_email, next_id, category_fk, auction_title, product_name, product_description, quantity, reserve_price, max_bids))

        conn.commit()
        conn.close()
        return redirect('/seller')

    conn.close()
    return render_template('seller_create.html', email=session['email'], categories=categories)

@app.route ('/seller/edit/<int:listing_id>', methods=['GET', 'POST'])
def edit_listing(listing_id):
    if 'email' not in session:
        return redirect('/login')

    seller_email = session['email']
    conn = get_db()


    bid_count = conn.execute("""
        SELECT COUNT(*) FROM Bids
        WHERE seller_email_fk = ? AND listing_ID_fk = ?""",
        (seller_email, listing_id)).fetchone()[0]

    if bid_count > 0:
        conn.close()
        return render_template('seller.html', error='This listing cant be edited, a bid exists on it')

    listing = conn.execute("""
        SELECT * FROM Auction_Listings
        WHERE seller_email_fk = ? AND listing_ID = ?
        """, (seller_email,listing_id)).fetchone()

    if request.method == 'POST':
        auction_title = request.form['auction_title']
        product_name = request.form['product_name']
        product_description = request.form['product_description']
        reserve_price = request.form['reserve_price']
        max_bids = request.form['max_bids']
        quantity = request.form['quantity']

        conn.execute("""
            UPDATE Auction_Listings
            SET auction_title = ?, product_name = ?, product_description = ?,
                reserve_price = ?, max_bids = ?, quantity = ?
            WHERE seller_email_fk = ? AND listing_ID = ?
        """, (auction_title, product_name, product_description, reserve_price, max_bids, quantity, seller_email, listing_id))

        conn.commit()
        conn.close()
        return redirect('/seller')

    conn.close()
    return render_template('seller_edit.html', email=seller_email, listing=listing)

@app.route('/seller/remove/<int:listing_id>', methods=['GET', 'POST'])
def remove_listing(listing_id):
    if 'email' not in session:
        return redirect('/login')

    seller_email = session['email']
    conn = get_db()

    if request.method == 'POST':
        removal_reason = request.form['removal_reason']

        conn.execute("""
            UPDATE Auction_Listings
            SET status = 0, removal_reason = ?
            WHERE seller_email_fk = ? AND listing_ID = ?
        """, (removal_reason, seller_email, listing_id))
        conn.commit()
        conn.close()
        return redirect('/seller')

    listing = conn.execute("""
        SELECT * FROM Auction_Listings
        WHERE seller_email_fk = ? AND listing_ID = ?
        """,(seller_email, listing_id)).fetchone()
    conn.close()
    return render_template('seller_remove.html', email=seller_email, listing=listing)


##################################################################################################################################################
#-------------------Profile Management Functions---------------------#############################################################################
##################################################################################################################################################

@app.route('/bidder/profile', methods=['GET', 'POST'])
def bidder_profile():
    if 'email' not in session:
        return redirect('/login')

    conn = get_db()
    email = session['email']

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        age = request.form['age']
        major = request.form['major']

        conn.execute("""
            UPDATE Bidders
            SET first_name = ?, last_name = ?, age = ?, major = ?
            WHERE email_fk = ?
            """, (first_name, last_name, age, major, email))

        new_password = request.form['new_password'].strip()
        if new_password:
            hashed_pw = hashlib.sha256(new_password.encode()).hexdigest()
            conn.execute("""
                UPDATE Users SET password = ? WHERE email_pk = ?
                    """, (hashed_pw, email))

        conn.commit()
        conn.close()
        return redirect('/bidder')

    bidder = conn.execute("""
    SELECT * FROM Bidders WHERE email_fk = ?
    """, (email,)).fetchone()
    conn.close()

    return render_template('bidder_profile.html', email=email, bidder=bidder)

@app.route('/seller/profile', methods=['GET', 'POST'])
def seller_profile():
    if 'email' not in session:
        return redirect('/login')

    conn = get_db()
    email = session['email']

    if request.method == 'POST':
        routing_number = request.form['routing_number']
        account_number = request.form['account_number']

        conn.execute("""
        UPDATE Sellers
        SET bank_routing_number = ?, bank_account_number = ?
        WHERE email_fk = ?
        """,(routing_number, account_number, email))


        new_password = request.form['new_password'].strip()
        if new_password:
            hashed_pw = hashlib.sha256(new_password.encode()).hexdigest()
            conn.execute("""
                UPDATE Users SET password = ? WHERE email_pk = ?""", (hashed_pw, email))

        conn.commit()
        conn.close()
        return redirect('/seller')

    seller = conn.execute(
        'SELECT * FROM Sellers WHERE email_fk = ?', (email,)
    ).fetchone()
    conn.close()

    return render_template('seller_profile.html', email=email, seller=seller)

#app route for user registration page
@app.route('/ureg', methods=['GET', 'POST'])
def ureg():

    return render_template('userRegistration.html')

#app route for submitting user registration:
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('selection-dropdown')
        email = request.form['email']
        password = request.form['password']
        cpassword = request.form['confirmpassword']

        if role == 'helpdesk' and (not ADMIN_PASSWORD or request.form.get('admin_password') != ADMIN_PASSWORD):
            flash('Invalid admin password.', 'error')
            return redirect('/ureg')

        #verifying whether the user already exists in the database.
        if duplicate_email(email) == True:
            return render_template('userRegistration.html', error = 'This email is already registered.',form_data = request.form)
        else:
            #need to add to the users table first
            add_users(email,password)
        if role == 'bidder':
            #get all the information from the form
            fname = request.form['fname']
            lname = request.form['lname']
            age = request.form['age']
            major = request.form['major']
            ccnum = request.form['ccnum']
            formatted_cnum = "-".join([ccnum[i:i+4] for i in range(0, len(ccnum), 4)])
            cctype = request.form['cctype']
            cvvnum = request.form['cvvnum']
            expdate = request.form['expdate']
            expyear = int(expdate[:4])
            expmonth = expdate[5:]#crashes while int
            owner_email = request.form['owneremail']

            zipcode = request.form['zip']
            stnum = request.form['stnum']
            stname = request.form['stname']

            address_id = get_address_id(zipcode,stnum,stname)

            conn = get_db()
            #print(f"expdate: {expdate}, expyear: {expyear}, expmonth: {expmonth}")
            #add to the bidders and the credit cards tables
            conn.execute('INSERT INTO BIDDERS VALUES (?,?,?,?,?,?)',(email, fname, lname, age, address_id, major))
            conn.execute('INSERT INTO Credit_Cards VALUES (?,?,?,?,?,?)',(ccnum, cctype, expmonth,expyear,cvvnum,owner_email))
            conn.commit()
            conn.close()
            flash('Registration Successful. Please Log in,', 'success')
            return redirect('/login')

        if role == 'seller':
            routing_num = request.form['routingnum']
            acc_num = request.form['accnum']
            balance = request.form['balance']
            conn = get_db()
            conn.execute('INSERT INTO Sellers VALUES (?, ?, ?, ?)', (email,routing_num,acc_num,balance))
            #conn.execute('INSERT INTO Credit_Cards VALUES (?,?,?,?,?,?)',())
            conn.commit()
            conn.close()
            flash('Registration Successful. Please Log in,', 'success')
            return redirect('/login')

        if role == 'helpdesk':
            admin_password = request.form.get('admin_password')
            if not ADMIN_PASSWORD or admin_password != ADMIN_PASSWORD:
                flash('Invalid admin password.', 'error')
                return redirect('/ureg')
            position = request.form['position']
            conn = get_db()
            conn.execute('INSERT INTO HelpDesk Values (?,?)',(email, position))
            conn.commit()
            conn.close()

            flash('Registration Successful. Please Log in,', 'success')
            return redirect('/login')


##################################################################################################################################################
#-------------------Bidding Functions---------------------#############################################################################
##################################################################################################################################################

@app.route("/place_bid", methods=['GET', 'POST'])
def place_bid():
    if 'email' not in session:
        return redirect('/login')
    bidder_email = session['email']
    bidAmt = int(request.form['bid'])
    seller_email = request.form['seller-email']
    listing_ID = request.form['listing-id']

    #sellers cannot bid on their own listings
    if bidder_email == seller_email:
        flash("You cannot bid on your own listing", "error")
        print("AAAAAAAAA")
        return redirect(f'/listing/{seller_email}/{request.form["listing-id"]}')


    bidAmt = int(request.form['bid'])
    remaining_bids = int(request.form['remaining-bids'])
    listing_room = f"listing_{seller_email}_{listing_ID}"
    resPrice = int(request.form['reserve-price'])


    conn = get_db()

    listing = get_listing_detail(conn, seller_email, listing_ID)

    # making sure that bidders cannot bid below the current highest bid
    if bidAmt <= listing['current_bid']:
        conn.close()
        flash("Cannot place bid lower than the current amount.", "error")
        return redirect(f'/listing/{seller_email}/{listing_ID}')

    #getting information about the current highest bidder
    max_bidder = conn.execute("""SELECT bidder_email_fk, MAX(bid_price)
                                 FROM Bids B, Auction_Listings A 
                                 WHERE A.seller_email_fk = B.seller_email_fk
                                 AND A.listing_ID = B.listing_ID_fk
                                 AND A.listing_ID = (?)
                              """, (listing_ID,)).fetchone()

    if max_bidder[0] == bidder_email: #So a user cannot bid twice in a row
        flash("Cannot place consecutive bids", "error")
        return redirect(f'/listing/{seller_email}/{listing_ID}')


    cur_bid_count = conn.execute("""
                                SELECT COUNT(*) FROM Bids B WHERE B.listing_ID_fk = ? AND B.seller_email_fk = ?
    """,(listing_ID,seller_email)).fetchone()[0]

    #conditions for auction end
    if listing['status'] == 0 or cur_bid_count >= listing['max_bids']:
        flash('This auction has ended',"error")
        return redirect(f'/listing/{seller_email}/{listing_ID}')

    #calculating the next id to insert into bids
    next_id = conn.execute("""
                           SELECT COALESCE(MAX(Bid_ID), 0) + 1
                           FROM Bids
                           """).fetchone()[0]
    conn.execute("INSERT INTO Bids (Bid_ID, seller_email_fk, listing_ID_fk, bidder_email_fk, bid_price) VALUES (?,?,?,?,?)",(next_id,seller_email,listing_ID,bidder_email,bidAmt))

    #updating the page for all users so that the latest changes are reflected
    socketio.emit('update page',{'message': f"New bid of {bidAmt} placed"},to=listing_room)

    # getting information of all the bidders to notify them of auction end
    all_bidders = conn.execute("""SELECT DISTINCT bidder_email_fk
                                  FROM Bids B
                                  WHERE B.listing_ID_fk = ?
                                    AND B.seller_email_fk = ?""", (listing_ID, seller_email,)).fetchall()
    #if after the current bid the number of bids is exhausted
    if cur_bid_count+1 >= listing['max_bids']:

        #if the auction ends and the max bid is greater than the reserve price it is a success
        if max_bidder[1] is not None and max_bidder[1] >= resPrice:
            #print("res price not met")
            conn.execute("Update Auction_Listings SET status = 0 WHERE listing_ID = (?)",(listing_ID,)) #changing the status if the number of max bids has been reached

            #iterating through each bidder and notifying them. Made a notifications table to store
            #notifications for users who are not logged in when the auction ends are stored here.
            for bidder in all_bidders:
                bidderEmail = bidder['bidder_email_fk']
                is_read = 0
                if bidderEmail == bidder_email:
                    payment_link = f"/payment/{listing['seller_email']}/{listing['listing_id']}"
                    msg = f"Congratulations! You have won the auction! Click  <a href = '{payment_link}'>here</a> to make your payment:"
                else:
                    msg = f"The auction for listing {listing_ID} has ended"

                conn.execute("""
                                INSERT INTO Notifications (user_email_fk, message,is_read) VALUES (?,?,?)""",(bidderEmail,msg,is_read))
                socketio.emit('auction ended', {'message':msg}, to=bidderEmail)
        #if reserve price is not met
        else:
            conn.execute("Update Auction_Listings SET status = 2 WHERE listing_ID = (?)", (listing_ID,)) #setting the status to 2 to signify that the auction has ended but the bid is insufficient.
            for bidder in all_bidders:
                bidderEmail = bidder['bidder_email_fk']
                message = f"The auction for listing {listing_ID} has ended but the reserve price was not met"

                conn.execute("""
                             INSERT INTO Notifications (user_email_fk, message)
                             VALUES (?, ?)""", (bidderEmail, message))
                socketio.emit('auction ended', {'message': message}, to=bidderEmail)


    # notifying the highest bidder if they have been outbid.
    if max_bidder[0] != None:
        msg = f"You have been outbid for listing {listing_ID}"
        conn.execute("""
                     INSERT INTO Notifications (user_email_fk, message)
                     VALUES (?, ?)""", (max_bidder[0], msg))
        socketio.emit('out bid', {'message': msg}, to = max_bidder[0])
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/')

#approute to view all of a users current bids.
@app.route('/view_bids')
def view_bids():
    if 'email' not in session:
        return redirect('/login')
    bidder_email = session['email']
    conn = get_db()
    #getting all the listings the user has bid on and passing them along with rendering the html page
    my_auctions = conn.execute('''SELECT
                        al.auction_title,
                        al.seller_email_fk,
                        al.listing_ID,
                        al.status,
                        MAX(b.bid_price) AS bidder_highest_bid,
                        (SELECT MAX(bid_price) FROM Bids WHERE listing_ID_fk = al.listing_ID) AS current_highest_bid
                    FROM Auction_Listings al
                    JOIN Bids b ON al.listing_ID = b.listing_ID_fk AND al.seller_email_fk = b.seller_email_fk
                    WHERE b.bidder_email_fk = ?
                    GROUP BY al.listing_ID,al.seller_email_fk''',(bidder_email,)).fetchall()

    conn.commit()
    conn.close()
    return render_template('/viewMyBids.html', auctions = my_auctions, user = bidder_email,email = session['email'])


@app.route("/payment/<seller_email>/<int:listing_id>")
def payment(seller_email,listing_id):
    if 'email' not in session:
        return redirect('/login')
    bidder_email = session['email']

    conn = get_db()
    #extracting the necessary info to auto fill the payment form
    ccinfo = conn.execute('''
                          SELECT *
                          FROM Credit_Cards
                          WHERE owner_email_fk = ?

                          ''', (bidder_email,)).fetchone()
    addrInfo = conn.execute('''
                                SELECT zipcode_fk, street_num, street_name
                                FROM Bidders B, Address A
                                WHERE B.home_address_id_fk = A.address_ID_pk AND B.email_fk = ?
                                    
                                ''',(bidder_email,)).fetchone()

    paymentAmt = conn.execute('''SELECT max(bid_price)
                                 FROM Bids b
                                 WHERE b.seller_email_fk = ? AND  b.listing_ID_fk = ? ''',(seller_email,listing_id)).fetchone()
    conn.commit()
    conn.close()

    return render_template('paymentPage.html', ccinfo = ccinfo, addrInfo = addrInfo, sellerEmail = seller_email, listing_id = listing_id, paymentAmt = paymentAmt,email = session['email'])
@app.route('/process_payment/<seller_email>/<int:listing_id>',methods=['GET', 'POST'])
def process_payment(seller_email,listing_id):
    if 'email' not in session:
        return redirect('/login')
    #storing necessary data that needs to be included in the transactions table
    paymentAmt = request.form.get('amount')
    curDate = date.today().strftime("%d/%m/%Y")
    bidder_email = session['email']

    conn = get_db()
    listing = get_listing_detail(conn, seller_email, listing_id)
    max_transaction_id = conn.execute("""
                           SELECT COALESCE(MAX(transaction_ID), 0) + 1
                           FROM Transactions
                           """).fetchone()[0]
    #Adding to transactions and changing the status in Auction_listings
    conn.execute('''INSERT INTO Transactions Values (?,?,?,?,?,?)''',(max_transaction_id,seller_email,listing_id,bidder_email,curDate,paymentAmt))

    conn.execute("""UPDATE Auction_Listings SET status = 2 WHERE listing_ID = ? AND seller_email_fk = ? """,(listing_id,seller_email,))


    #delete win notification after purchase
    conn.execute("""
        DELETE FROM Notifications
        WHERE user_email_fk = ? AND message LIKE ?
        """, (bidder_email, f'%/payment/{seller_email}/{listing_id}%'))



    conn.commit()
    conn.close()


    #return redirect(f'/receipt/{listing['seller_email']}/{listing['listing_id']}')
    return redirect(f"/receipt/{listing['seller_email']}/{listing['listing_id']}")

@app.route('/receipt/<seller_email>/<int:listing_id>')
def receipt(seller_email,listing_id):
    if 'email' not in session:
        return redirect('/login')
    conn = get_db()
    listing = get_listing_detail(conn, seller_email, listing_id)
    conn.commit()
    conn.close()


    return render_template('receiptPage.html', listing = listing)


##################################################################################################################################################
#-------------------Rating Functions---------------------#########################################################################################
##################################################################################################################################################

@app.route('/rating_link/<seller_email>/<int:listing_id>')
def rating_link(seller_email,listing_id):
    if 'email' not in session:
        return redirect('/login')

    bidder_email = session['email']
    conn = get_db()

    #check if rated already
    rated = conn.execute("""
        SELECT * FROM Ratings
        WHERE bidder_email_fk = ? AND seller_email_fk = ?
        """, (bidder_email, seller_email)).fetchone()

    if rated:
        conn.close()
        return redirect('/bidder')

    listing = get_listing_detail(conn, seller_email, listing_id)
    #conn.commit()
    conn.close()

    return render_template('ratingPage.html',listing = listing)


@app.route('/clear_notifications/<int:notification_id>')
def clear_notifications(notification_id):
    #allowing users to dismiss/delete notifications
     if 'email' in session:
         conn = get_db()
         conn.execute("""DELETE FROM Notifications WHERE notification_ID = ? AND user_email_fk = ?""",(notification_id,session['email'],))
         conn.commit()
         conn.close()
     return redirect('/bidder',)

@app.route('/insert_rating',methods=['GET', 'POST'])
def insert_rating():
    if 'email' not in session:
        return redirect('/login')
    bidder_email = session['email']
    seller_email = request.form.get('seller-email')
    rating = int(request.form.get('rating'))
    desc = request.form.get('desc')
    curDate = date.today().strftime("%d/%m/%Y")

    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO Ratings VALUES(?,?,?,?,?)",(bidder_email, seller_email, curDate, rating, desc))
    conn.commit()
    conn.close()

    return redirect('/bidder',)


##################################################################################################################################################
#-------------------Chatroom Functions---------------------#######################################################################################
##################################################################################################################################################
#chatroom useful for users to talk to eachother.
rooms = {}
def generate_unique_code(length):
    while True:
        code = ""
        for i in range(length):
            code += random.choice(ascii_uppercase)
        if code not in rooms:
            break
    return code

@app.route("/chatHome",methods=['GET', 'POST'])
def chatHome():

    #session.clear()
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        join = request.form.get('join',False)
        create = request.form.get('create',False)
        if not name:
            return render_template("chatHome.html", error = 'please enter a name', code = code, name = name)
        if join != False and not code:
            return render_template("chatHome.html", error = 'please enter a room code', code = code, name = name)

        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages":[]}
        elif code not in rooms:
            return render_template("chatHome.html", error = 'room does not exist', code = code, name = name)

        session["room"] = room
        session["name"] = name

        return redirect(url_for('chatRoom'))


    return render_template("chatHome.html")




@app.route("/chatRoom")
def chatRoom():

    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms: #logic so a user cannot access a chat room by changing the url
        return redirect(url_for('chatHome'))

    return render_template("chatRoom.html", code = room)

@socketio.on('notify')
def notify(auth):
    email = session['email']
    if email:
        join_room(email)

@socketio.on('join_listing')
def join_listing(data):
    listing_id = data.get('listing_id')
    seller_email = data.get('seller_email')

    if listing_id and seller_email:
        room = f"listing_{seller_email}_{listing_id}"
        join_room(room)
        print(f"User joined the room {room}")


@socketio.on('connect')
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has joined the room"}, to = room)
    rooms[room]["members"] += 1
    print(f"{name} joined the room: {room}")

@socketio.on('disconnect')
def disconnect():
    room = session.get("room")
    name = session.get("name")

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    send({"name": name, "message": "has left the room"}, to=room)
    leave_room(room)
    print(f"{name} left the room: {room}")

@socketio.on('message')
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    content = {
        "name": session.get("name"),
        "message": data['data'],
    }

    send(content, to = room)
    rooms[room]["messages"].append(data['data'])
    print(f"{session.get('name')} sent message: {data['data']}")




##################################################################################################################################################
#-------------------HelpDesk Functions---------------------#######################################################################################
##################################################################################################################################################



#displays unassignned request and claimed requests
@app.route('/helpdesk')
def helpdesk():
    if 'email' not in session:
        return redirect('/login')

    conn = get_db()
    #get all unassigned helpdesk requests
    unassigned = conn.execute("""
        SELECT * FROM Requests
        WHERE helpdesk_staff_email_fk IS NULL
        AND request_status = 0
    """).fetchall()

    #get all helpdesk requests assigned to current user
    my_requests = conn.execute("""
        SELECT * FROM Requests
        WHERE helpdesk_staff_email_fk = ?
        AND request_status = 0
    """,(session['email'],)).fetchall()
    conn.close()

    return render_template('helpdesk.html', email=session['email'],
                           unassigned=unassigned, my_requests = my_requests)

#assigns a helpdesk staff to an unassigned request
@app.route('/helpdesk/claim', methods=['POST'])
def claim_request():
    if 'email' not in session:
        return redirect('/login')

    request_id = request.form['request_id']#get request id from the form
    conn = get_db()

    #assigns helpdesk staffs email to the request
    #removes request from unassigned list to the staff's list
    conn.execute("""
        UPDATE Requests
        SET helpdesk_staff_email_fk = ?
        WHERE request_id_pk = ?
    """, (session['email'], request_id))
    conn.commit()
    conn.close()
    return redirect('/helpdesk')


#allows a seller to submit a new category request
@app.route('/seller/request', methods=['GET','POST'])
def submit_category_request():
    if 'email' not in session:
        return redirect('/login')

    if request.method == 'POST':
        request_desc = request.form['request_desc'] #category description
        seller_email = session['email'] #get seller email from session

        conn = get_db()
        #insert request to unassigned list with status=0
        #request type is general'
        conn.execute("""
        INSERT INTO Requests(sender_email_fk, request_type, request_desc, request_status)
        VALUES(?, 'general', ?, 0)
        """
        , (seller_email, request_desc))

        conn.commit()
        conn.close()
        role = session.get('role')
        return redirect('/seller' if role == 'Seller' else '/bidder')

    return render_template('seller_request.html', email=session['email'])

@app.route('/bidder/request', methods=['GET','POST'])
def bidder_request():
    return submit_category_request()

#allows helpdesk staff to approve a category request
@app.route('/helpdesk/approve/<int:request_id>', methods=['GET', 'POST'])
def approve_request(request_id):
    if 'email' not in session:
        return redirect('/login')

    conn = get_db()
    #get the request being approved
    req = conn.execute(
        'SELECT * FROM Requests WHERE request_id_pk = ?', (request_id,)).fetchone()

    if request.method == 'POST':
        category_name = request.form['category_name']
        parent_category = request.form['parent_category'] or 'Root'

        #used to check if this category already exists
        existing = conn.execute(
            'SELECT * FROM Categories WHERE category_name = ?', (category_name,)
        ).fetchone()


        if existing:
            #renders form with error message
            categories=conn.execute(
                'SELECT category_name FROM Categories ORDER BY category_name'
            ).fetchall()
            conn.close()
            return render_template('helpdesk_approve.html',
                                   email=session['email'],
                                   req=req,
                                   categories=categories,
                                   error='Category already exists')


        #inserts the new category into the hierarchy
        conn.execute("""
        INSERT INTO Categories (category_name, parent_category_fk) VALUES(?,?)
        """, (category_name, parent_category))

        #request is marked as complete, status=1
        conn.execute("""
        UPDATE Requests
        SET request_status = 1,
            helpdesk_staff_email_fk = ?
        WHERE request_id_pk = ?
        """, (session['email'], request_id))

        conn.commit()
        conn.close()
        return redirect('/helpdesk')
    #loads all categories for the dropdown menu
    categories = conn.execute("""
    SELECT category_name FROM Categories ORDER BY category_name""").fetchall()
    conn.close()

    return render_template('helpdesk_approve.html',
                           email=session['email'],
                           req=req,
                           categories=categories)


@app.route('/helpdesk/email_change/<int:request_id>', methods=['POST'])
def email_change(request_id):
    if 'email' not in session:
        return redirect('/login')

    new_email = request.form['new_email']
    conn=get_db()

    req = conn.execute('SELECT * FROM Requests WHERE request_id_pk = ?', (request_id,)).fetchone()
    old_email = req['sender_email_fk']

    conn.commit()
    conn.close()
    flash('EMail updated successfully.','success')
    return redirect('/helpdesk')




##################################################################################################################################################
#-------------------Watchlist Functions---------------------#######################################################################################
##################################################################################################################################################

@app.route('/watchlist')
def watchlist():
    if 'email' not in session:
        return redirect('/login')

    bidder_email = session['email']
    conn = get_db()

    items = conn.execute("""
        SELECT
            al.seller_email_fk AS seller_email,
            al.listing_ID AS listing_id,
            al.auction_title,
            al.product_name,
            al.status,
            al.max_bids,
            COALESCE(MAX(b.bid_price), 0) AS current_bid,
            al.max_bids - COUNT(b.Bid_ID) AS remaining_bids
        FROM Watchlist w
        JOIN Auction_Listings al
            ON w.seller_email_fk = al.seller_email_fk
            AND w.listing_ID_fk = al.listing_ID
        LEFT JOIN Bids b
            ON al.seller_email_fk = b.seller_email_fk
            AND w.listing_ID_fk = b.listing_ID_fk
        WHERE w.bidder_email_fk = ?
        GROUP BY al.seller_email_fk, al.listing_ID       
    """,(bidder_email,)).fetchall()
    conn.close()
    return render_template('watchlist.html', email=bidder_email, items=items)

@app.route('/watchlist/add/<seller_email>/<int:listing_id>', methods=['POST'])
def add_to_watchlist(seller_email, listing_id):
    if 'email' not in session:
        return redirect('/login')

    bidder_email = session['email']
    conn = get_db()

    existing = conn.execute("""
        SELECT * FROM Watchlist
        WHERE bidder_email_fk = ? AND seller_email_fk = ? AND listing_ID_fk = ?
        """, (bidder_email, seller_email, listing_id)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO Watchlist(bidder_email_fk, seller_email_fk, listing_ID_fk)
            VALUES(?,?,?)
            """, (bidder_email, seller_email, listing_id))
        conn.commit()
    conn.close()
    return redirect(f'/listing/{seller_email}/{listing_id}')

@app.route('/watchlist/remove/<seller_email>/<int:listing_id>', methods=['POST'])
def remove_from_watchlist(seller_email, listing_id):
    if 'email' not in session:
        return redirect('/login')

    bidder_email = session['email']
    conn = get_db()
    conn.execute("""
        DELETE FROM Watchlist
        WHERE bidder_email_fk = ? AND seller_email_fk = ? AND listing_ID_fk = ?
    """,(bidder_email, seller_email, listing_id))
    conn.commit()
    conn.close()
    return redirect(f'/listing/{seller_email}/{listing_id}')

###################################################################################################################
###################################################################################################################
###################################################################################################################

@app.route('/seller/promote/<int:listing_id>', methods=['GET', 'POST'])
def promote_listing(listing_id):
    if 'email' not in session:
        return redirect('/login')

    seller_email = session['email']
    conn = get_db()
    listing = get_listing_detail(conn, seller_email, listing_id)


    if not listing or listing['status'] != 1:
        conn.close()
        return redirect('/seller')

    already_promoted = conn.execute("""
        SELECT * FROM Promotions
        WHERE seller_email_fk = ? AND listing_id_fk = ?
        """, (seller_email, listing_id)).fetchone()

    fee = round(listing['reserve_price'] * .05, 2)

    if request.method == 'POST':
        if already_promoted:
            conn.close()
            return redirect('/seller')

        conn .execute("""
            INSERT INTO Promotions (seller_email_fk, listing_id_fk, fee_paid)
            VALUES(?,?,?)
        """, (seller_email, listing_id, fee))
        conn.commit()
        conn.close()
        return redirect('/seller')
    conn.close()

    return render_template('seller_promote.html', email = seller_email, listing =listing,
                           fee = fee, already_promoted = already_promoted)



if __name__ == '__main__':
    socketio.run(app, debug=os.environ.get("FLASK_DEBUG") == "1", allow_unsafe_werkzeug=True)

