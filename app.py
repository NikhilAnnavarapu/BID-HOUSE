import os
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime
from web3 import Web3, HTTPProvider
import json
import time

app = Flask(__name__)
app.secret_key = "1234567890"

x = "../build/contracts/AuctionBid.json"
blockchainServer = "HTTP://127.0.0.1:7545"

def connectWithContract(wallet, artifact=x):
    web3 = Web3(HTTPProvider(blockchainServer))  # it is connecting with server
    print('Connected with Blockchain Server')

    if wallet == 0:
        web3.eth.defaultAccount = web3.eth.accounts[0]
    else:
        web3.eth.defaultAccount = wallet
    print('Wallet Selected')

    with open(artifact) as f:
        artifact_json = json.load(f)
        contract_abi = artifact_json['abi']
        contract_address = artifact_json['networks']['5777']['address']

    contract = web3.eth.contract(abi=contract_abi, address=contract_address)
    print('Contract Selected')
    return contract, web3

# Database Connection
cluster = MongoClient("mongodb://127.0.0.1:27017")
db = cluster['auction_project']
users = db['users']
items = db['auction_items']
bids = db['bids']

# File Upload Configuration
UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    """Render the homepage."""
    return render_template("index.html")

@app.route("/register")
def register_page():
    """Render the signup page."""
    return render_template("signup.html")

@app.route("/login")
def login_page():
    """Render the login page."""
    return render_template("login.html")

@app.route("/home")
def home_page():
    # Get all items from MongoDB
    auction_items = list(items.find({}))
    
    # Convert ObjectId to string for each item
    for item in auction_items:
        item['_id'] = str(item['_id'])
    
    return render_template("home.html",items=auction_items    )

@app.route("/item")
def add_items():
    return render_template("sell_items.html")

@app.route("/signup", methods=['POST'])
def user_register():
    """Handle user signup."""
    username = request.form["Username"]
    email = request.form["Email"]
    password = request.form["Password"]
    confirm_password = request.form["ConfirmPassword"]

    if password != confirm_password:
        return render_template("signup.html", status="Passwords don't match")

    if users.find_one({"username": username}):
        return render_template("signup.html", status="User already exists")

    users.insert_one({"username": username, "email": email, "password": password})
    return render_template("signup.html", status="Registration Successful")

@app.route("/login", methods=['POST'])
def user_login():
    """Handle user login."""
    username = request.form.get("Username")
    password = request.form.get("Password")

    user = users.find_one({"username": username})
    if user and user["password"] == password:
        session['user'] = username
        return redirect("/home")

    return render_template("login.html", status="Invalid Login Credentials")

@app.route("/sellitems")
def sell_items():
    """Render the Sell Items page."""
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template("sellitems.html")

@app.route("/add_item", methods=['POST'])
def add_item():
    """Handle form submission for adding auction items."""
    if 'user' not in session:
        return redirect(url_for('login_page'))

    try:
        item_name = request.form["itemName"]
        category = request.form["category"]
        description = request.form["description"]
        base_price = int(request.form["basePrice"])
        seller = session["user"]

        # Handle single image upload
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            print("Image file received:", file.filename)
            if file and file.filename != '' and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    print(f"✅ Successfully saved image: {filepath}")
                    image_url = filename
                except Exception as e:
                    print(f"❌ Error saving image: {e}")
                    return f"Error uploading image: {str(e)}", 500
            else:
                print("❌ Invalid file or filename:", file.filename if file else None)
        else:
            print("❌ No image file in request")

        # First, insert into MongoDB
        item = {
            "name": item_name,
            "category": category,
            "description": description,
            "base_price": base_price,
            "current_price": base_price,  # Initially, current price is same as base price
            "seller": seller,
            "current_bidder": seller,  # Initially, seller is the current bidder
            "image": image_url,  # Store only the filename
            "created_at": datetime.utcnow()
        }
        response = items.insert_one(item)
        item_id = str(response.inserted_id)
        print("MongoDB Item ID:", item_id)

        try:
            # Connect to blockchain
            print("Connecting to blockchain...")
            contract, web3 = connectWithContract(0)  # Using the new function name
            if not contract:
                print("❌ Failed to connect to blockchain")
                return redirect(url_for('home_page'))

            print("Connected to blockchain, adding item...")
            # Add item to blockchain
            tx_hash = contract.functions.addItem(
                seller,              # bidder (initially empty string)
                seller,          # owner
                item_name,       # item name
                item_id,         # MongoDB item ID
                int(base_price),      # base price
                int(base_price)       # current price (initially same as base price)
            ).transact()

            # Wait for transaction to be mined
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            print("✅ Item added to blockchain")
            print("Transaction hash:", tx_hash.hex())

        except Exception as e:
            print(f"❌ Error in blockchain connection: {str(e)}")
        return redirect(url_for('home_page'))

    except Exception as e:
        print(f"❌ Error in add_item: {str(e)}")
        return f"Error adding item: {str(e)}", 500

@app.route("/bid/<item_id>", methods=['GET', 'POST'])
def place_bid(item_id):
    if 'user' not in session:
        return redirect(url_for('login_page'))
    try:
        item = items.find_one({"_id": ObjectId(item_id)})
        if not item:
            return "Item not found", 404

        if request.method == 'POST':
            bid_amount = float(request.form.get('bid_amount'))
            print(bid_amount)
            
            # Validate bid amount
            if bid_amount <= float(item['current_price']):
                return redirect(url_for('item_details', item_id=item_id))

            # Get user details
            user = users.find_one({"username": session['user']})
            if not user:
                return "User not found", 404

            # Connect to blockchain
            contract, web3 = connectWithContract(0)
            if not contract:
                return redirect(url_for('item_details', item_id=item_id))

            try:
                # Place bid on blockchain
                tx_hash = contract.functions.placeBid(
                    str(item_id),     # item id
                    session['user'],   # bidder
                    int(bid_amount)    # new price
                ).transact()
                
                # Wait for transaction to be mined
                web3.eth.wait_for_transaction_receipt(tx_hash)

                # Update item in MongoDB
                items.update_one(
                    {"_id": ObjectId(item_id)},
                    {"$set": {
                        "current_price": bid_amount,
                        "current_bidder": session['user']
                    }}
                )

                return redirect(url_for('item_details', item_id=item_id))

            except Exception as e:
                print(f"Blockchain transaction error: {e}")
                return redirect(url_for('item_details', item_id=item_id))
                
        return redirect(url_for('item_details', item_id=item_id))

    except Exception as e:
        print(f"Error in place_bid: {e}")
        return "Error processing bid", 500

@app.route("/get_auction_items", methods=['GET'])
def get_auction_items():
    """API to fetch all auction items."""
    items_list = list(items.find({"seller":session['user']}))
    for item in items_list:
        item["_id"] = str(item["_id"])
    return jsonify(items_list)

@app.route("/item/<item_id>")
def item_details(item_id):
    """
    Display details of a specific auction item.
    """
    try:
        # Convert string ID to ObjectId
        item = items.find_one({"_id": ObjectId(item_id)})
        if item:
            # Get all bids for this item
            item_bids = list(bids.find({"item_id": item_id}).sort("amount", -1))
            return render_template("item_details.html", item=item, bids=item_bids)
        else:
            return "Item not found", 404
    except Exception as e:
        print(f"Error fetching item details: {e}")
        return "Error fetching item details", 500

@app.route("/place_bid/<item_id>")
def get_item_details(item_id):
    """Fetch item details from blockchain."""
    try:
        print(f"Fetching details for item: {item_id}")
        contract, web3 = connectWithContract(0)
        
        # Get the item details from MongoDB first
        item_data = items.find_one({"_id": ObjectId(item_id)})
        if not item_data:
            return jsonify({"error": "Item not found"}), 404
            
        # Convert ObjectId to string for the contract call
        item_id_str = str(item_data['_id'])
        item = contract.functions.getItem(item_id_str).call()
        
        # Convert timestamp to readable format
        timestamp = datetime.fromtimestamp(item[6])
        formatted_time = timestamp.strftime("%Y-%m-%d %I:%M %p")
        
        # Create list with formatted time
        formatted_item = list(item[:6]) + [formatted_time]
        print("Item details:", formatted_item)
        return render_template("place_bid.html", item=formatted_item)
    except Exception as e:
        print(f"Error fetching item details: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/submit_bid/<item_id>", methods=['POST'])
def submit_bid(item_id):
    """Handle bid submission."""
    try:
        if 'user' not in session:
            return redirect(url_for('login_page'))
            
        bid_amount = int(request.form['bidAmount'])
        
        contract, web3 = connectWithContract(0)
        
        print(f"Placing bid: Item={item_id}, Bidder={session['user']}, Amount={bid_amount}")
        
        # Call the placeBid function on the smart contract
        tx_hash = contract.functions.placeBid(
            item_id,
            session['user'],
            bid_amount
        ).transact()
        
        # Wait for transaction to be mined
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Transaction receipt: {receipt}")
        
        # Force a small delay to ensure the blockchain state is updated
        time.sleep(2)
        
        # Redirect back to the place bid page to show updated information
        return redirect(url_for('get_item_details', item_id=item_id))
        
    except Exception as e:
        print(f"Error submitting bid: {e}")
        return f"Error submitting bid: {str(e)}", 500

@app.route("/logout")
def logout():
    """Handle user logout."""
    session.pop('user', None)
    return redirect(url_for('login_page'))

if __name__ == "__main__":
    app.run(debug=True)