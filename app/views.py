from app import app
from flask import redirect, render_template, request, session, url_for, flash, Flask
import pymysql
from random import randint
from config import config as myConfig
# from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import uuid
import hashlib
from decimal import Decimal
# from ast import literal_eval

# opens up SQL connection with credentials
def openDb():
	db = pymysql.connect(
        myConfig.MYSQL_DATABASE_HOST,
        myConfig.MYSQL_DATABASE_USER,
        myConfig.MYSQL_DATABASE_PASSWORD,
        myConfig.MYSQL_DATABASE_DB)
	return(db) # return database connection

# display starting page for Marta application
@app.route('/')
def start():
	return render_template("home.html")

# WORKS
@app.route('/login', methods=['POST', 'GET'])
def login():

	# GET request method just renders template

	if request.method == 'POST':

		username = request.form['username'] # get value from username input
		password = request.form['password'] # get value from password input

		db = openDb()
		dbCursor = db.cursor()

		# default until sql query
		userTuple = None
		storedPassword = None

		try:
			dbCursor.execute("""SELECT * FROM `User` WHERE `Username` = %s""", [username])

			userTuple = dbCursor.fetchall()[0]  # gets tuple of user information
			storedPassword = userTuple[1]		# gets hashed password value

		except: # if username doesn't exist - query fails
			error = 'Invalid Username'
			return render_template('login.html', userVal = "", passVal = "", error = error) # reset inputs for username and password

		# validate input password and stored (database) password
		if check_password(storedPassword, password):

			# username/password correct - get admin status
			checkAdmin = userTuple[2]

			if checkAdmin == 0: # passenger status
				return redirect(url_for('pass_dashboard', username=username)) # pass in username value to passenger dashboard html page
			else: # admin status
				return redirect(url_for('admin_dashboard'))

		else:
			# input password and stored password aren't equal
			error = 'Incorrect Password'
			return render_template('login.html', error = error, userVal = "", passVal = "") # reset inputs for username and password

		dbCursor.close()
		db.close()

	return render_template('login.html', error = None, userVal = "", passVal = "")

# WORKS
@app.route('/register', methods=['POST', 'GET'])
def register():

	# GET request method just renders template

	if request.method == 'POST':

		username = request.form['username'] 		# get value from username input
		email = request.form['email'] 				# get value from email input
		password = request.form['password']			# get value from password input
		hash_pass = generate_hash(password)
		breezecard = request.form['breezecard']		# get value from breezecard input
		breezecard = breezecard.replace(" ", "")	# remove extraneous spaces

		db = openDb()
		dbCursor = db.cursor()

		try:
			# check uniqueness of username - if works, user created
			dbCursor.execute("""INSERT INTO `User`(`Username`, `Password`, `IsAdmin`) VALUES (%s, %s, 0)""", [username, hash_pass])

		except: # query fails if username (primary key) already exists
			error = 'Username already taken'
			return render_template('registration_page.html', error = error, reg_user_val = "", reg_pass_val = password, reg_confirm_val = password, reg_email_val = email)
			# reset value for username - save other inputs

		# user is default a passenger - has an email
		try:
			# check uniqueness of email - if works, passenger created
			dbCursor.execute("INSERT INTO `Passenger`(`Username`, `Email`) VALUES (%s, %s)", [username, email])

		except: # query fails if email (unique) already exists
			error = 'Account already exists for this email. Incorrect credentials'
			return render_template('registration_page.html', error = error, reg_user_val = username, reg_pass_val = password, reg_confirm_val = password, reg_email_val = "")
			# reset value for email - save other inputs

		# user selects "Doesn't Have Breezecard" - input is empty
		if breezecard == "":
			# generate new breezecard, insert it into database
			generate_breezecard(dbCursor, username)

		## for using "Have Breezecard", check if Breezecard is already in the system
		else:

			try:
				# try to insert breezecard into database
				dbCursor.execute("""INSERT INTO `Breezecard`(`BreezecardNum`, `Value`, `BelongsTo`) VALUES (%s, 0, %s)""", [breezecard, username])

			except: # breezecard already exists in database - query fails

				countNull = None

				try:
					# will either return 0 or 1 tuple(s)
					dbCursor.execute("""SELECT * FROM `Breezecard` WHERE `BreezecardNum` = %s AND `BelongsTo` IS NULL""", [breezecard])

					countNull = dbCursor.rowcount # number of tuples

				except: # query fails for some reason - generate random card and go to passenger dashboard

					generate_breezecard(dbCursor, username)
					return redirect(url_for('pass_dashboard', username=username))

				# only works if above query worked
				if countNull > 0: # this breezecard has a NULL owner
					try:
						# card exists but doesn't belong to anyone (i.e. BelongsTo = NULL)
						dbCursor.execute("""UPDATE `Breezecard` SET `BelongsTo` = %s WHERE `BreezecardNum` = %s""", [username, breezecard])

					except: # query fails for some reason - generate random card and go to passenger dashboard

						generate_breezecard(dbCursor, username)
						return redirect(url_for('pass_dashboard', username=username))

				else: # breezecard has an associated owner

					# get current timestamp
					dateTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

					# create Conflict (i.e. suspend card)
					try:

						dbCursor.execute("""INSERT INTO `Conflict`(`Username`, `BreezecardNum`, `DateTime`) VALUES (%s, %s, %s)""", [username, breezecard, dateTime])
						generate_breezecard(dbCursor, username) # generate new breezecard for username

					except: # query fails - there already exists a conflict for this username and breezecard; generate new breezecard and redirect to passenger dashboard

						generate_breezecard(dbCursor, username)
						return redirect(url_for('pass_dashboard', username=username))

		db.commit()
		dbCursor.close()
		db.close()

		# submit inputs and go right to passenger dashboard
		return redirect(url_for('pass_dashboard', username=username))

	return render_template('registration_page.html', error = None, reg_user_val = "", reg_pass_val = "", reg_confirm_val = "", reg_email_val = "")

# generates a breezecard not in the DB and inserts it into DB with specified username
def generate_breezecard(dbCursor, username):

	# generate random string of 16 numbers
	cardNumber = ""
	for x in range(0, 16):
		cardNumber += str(randint(0,9))

	# Checks if Random Breezecard already in database - if not generate again
	z = True
	while(z):

		try:
			# attempt to insert breezecard number into database - value of $0.00
			dbCursor.execute("""INSERT INTO `Breezecard`(`BreezecardNum`, `Value`, `BelongsTo`) VALUES (%s, 0, %s)""", [cardNumber, username])
			z = False # end loop if successful

		except:
			# resets breezecard string
			cardNumber = ""
			for x in range(0, 16):
				cardNumber += str(randint(0,9))

# generate hashcode for character string
def generate_hash(password):
	salt = str(uuid.uuid4().hex)[0:23]
	return hashlib.sha256(salt.encode() + password.encode()).hexdigest()[0:24] + ':' + salt

# compare hash values to see if equal
def check_password(hash_pass, user_password):
	password, salt = hash_pass.split(':')
	return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()[0:24]

@app.route('/admin_dashboard')
def admin_dashboard():
	return render_template('admin_dashboard.html')

@app.route('/passenger_dashboard/<username>')
def pass_dashboard(username):
	return render_template('passenger_dashboard.html', username=username)

@app.route('/station_management', methods=['POST', 'GET'])
def station_management():

	db = openDb()
	dbCursor = db.cursor()

	filter_name = None
	error = None

	station_listing = []

	try:
		dbCursor.execute("""SELECT * FROM `Station`""")

		station_listing = dbCursor.fetchall()

	except:
		error = "Couldn't get stations at the moment"
		return render_template('station_management.html', station_listing= station_listing, error = error, station_info=station_info, nearest_intersection=None, filter_name = filter_name)


	# if reach here no exception happened and station_listing has value
	temp = []
	for station in station_listing:
		status = ()
		if station[3] == 0: # closed status
			status = ("Open", )
		elif station[3] == 1:
			status = ("Closed", )

		station = station + status
		temp.append(station)

	station_listing = temp
	station_info = station_listing

	# create a new station or view a station
	if request.method == "POST":
		if "newStation" in request.form:
			station_name = request.form['station_name']
			stop_id = request.form['stop_id']
			entry_fare = request.form['entry_fare']
			station_type = request.form['station_type']
			intersection = ""
			isTrain = 1

			if station_type == "bus":
				intersection = request.form['nearest_intersection']
				print(intersection)
				isTrain = 0

			try:
				status = request.form['station_status']
			except:
				status = 1
				print("closed")
			print(status)
			try:
				dbCursor.execute("""INSERT INTO `Station` VALUES (%s, %s, %s, %s, %s)""",
									[stop_id, station_name, entry_fare, status, isTrain])
				db.commit()
				print("completed")
				if station_type == "bus":
					dbCursor.execute("""INSERT INTO `BusStationIntersection` VALUES (%s, %s)""",
									[stop_id, intersection])
					db.commit()
			except:
				print("Not unique StopID")
				error = "StopId already in the database"
			

		elif "station_filter" in request.form:

			filter_type = request.form['filter']

			if filter_type == "station_name_abc":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `Name` ASC""")
				filter_name = "Station Name Alphabetically"

			elif filter_type == "station_name_xyz":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `Name` DESC""")
				filter_name = "Station Name Reverse Alphabetical"

			elif filter_type == "stopid_abc":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `StopID` ASC""")
				filter_name = "Stop ID Alphabetically"

			elif filter_type == "stopid_xyz":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `StopID` DESC""")
				filter_name = "Stop ID Reverse Alphabetically"

			elif filter_type == "fare_low":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `EnterFare` ASC""")
				filter_name = "Fare Lowest to Highest"

			elif filter_type == "fare_high":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `EnterFare` DESC""")
				filter_name = "Fare Highest to Lowest"

			elif filter_type == "status_open":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `ClosedStatus` ASC""")
				filter_name = "Status: Open -> Closed"

			elif filter_type == "status_closed":
				dbCursor.execute("""SELECT * FROM `Station` ORDER BY `ClosedStatus` DESC""")
				filter_name = "Status: Closed -> Open"

			station_listing = dbCursor.fetchall()
			temp = []
			for station in station_listing:
				status = ()
				if station[3] == 0:
					status = ("Open", )
				elif station[3] == 1:
					status = ("Closed", )
				station = station + status
				temp.append(station)
			station_listing = temp
			station_info = station_listing

	return render_template('station_management.html', station_listing= station_listing, error = error, station_info=station_info, nearest_intersection=None, filter_name = filter_name)

@app.route('/view_station/<stopid>', methods=['POST', 'GET'])
def view_station(stopid):
	db = openDb()
	dbCursor = db.cursor()
	error = None
	dbCursor.execute("SELECT * FROM `Station` WHERE `StopID` = %s", [stopid])
	station_info = dbCursor.fetchone()
	nearest_intersection = "Nearest Intersection: Not available for Train Stations"
	if station_info[4] == 0:
		dbCursor.execute("SELECT `Intersection` FROM `BusStationIntersection` WHERE `StopId` = %s", [stopid])
		nearest_intersection = "Nearest Intersection is " + dbCursor.fetchone()[0]

	if request.method == "POST":
		new_fare = request.form['new_fare']
		print(new_fare)
		print(stopid)
		try:
			status = request.form['station_status']
		except:
			status = 1
		print(status)
		if new_fare:
			dbCursor.execute("""UPDATE `Station`
								SET `EnterFare` = %s, `ClosedStatus` = %s
								WHERE `StopID` = %s""",
								[new_fare, status, stopid])
		else:
			dbCursor.execute("""UPDATE `Station`
								SET `ClosedStatus` = %s
								WHERE `StopID` = %s""",
								[status, stopid])
	db.commit()

	return render_template('view_station.html', station_info=station_info, nearest_intersection=nearest_intersection, error=error)

# WORKS
def get_suspended_cards():

	suspendedList = []

	db = openDb()
	dbCursor = db.cursor()

	try:
		# retrieve card information for suspended cards (username is new user, belongsTo is old user)
		dbCursor.execute("""SELECT BreezecardNum, Username, DateTime, BelongsTo
							FROM Conflict AS C
							NATURAL JOIN Breezecard AS B
							WHERE C.BreezecardNum = B.BreezecardNum ORDER BY BreezecardNum""");

		suspendedCards = dbCursor.fetchall()

	except:
		return "Couldn't retrieve list of suspended breezecards"

	# create table rows for suspended card table
	for card in suspendedCards:
		suspendedRow = []
		count = 0
		for data in card:
			if count == 0: # add spaces to breezecard number
				suspendedRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
			else:
				suspendedRow.append(data)
			count += 1

		suspendedList.append(suspendedRow)


	db.commit()
	dbCursor.close()
	db.close()

	return suspendedList

# WORKS
@app.route('/suspended', methods=['POST', 'GET'])
def suspended():

	db = openDb()
	dbCursor = db.cursor()

	error = None
	suspendedList = []

	suspendedReturn = get_suspended_cards()

	if type(suspendedReturn) is str: # method returned an error message
		return render_template("suspended.html", suspendedList=suspendedList, error=suspendedReturn)
	else: # method return list of suspended cards
		suspendedList = suspendedReturn


	if request.method == "POST": # either button to assign card is clicked

		# no breezecard is selected
		if "selected_suspended" not in request.form: # works
			error = "Please select a breezecard to resolve."
			return render_template("suspended.html", suspendedList=suspendedList, error=error)


		# only reached if statement above fails condition

		selectedValue = request.form['selected_suspended'] # row selected in table
		selectedValue = selectedValue.split(",")
		subList = []
		for value in selectedValue:
			value = value.replace("'", "")
			value = value.replace(" ", "")
			value = value.replace("(", "")
			value = value.replace(")", "")
			subList.append(value)

		cardNumber = subList[0]
		newOwner = subList[1]
		prevOwner = subList[2]

		if "top-button" in request.form: # assign card to new owner

			cardCount = None 	# placeholder

			try:
				# get number of breezecards for previous owner
				dbCursor.execute("""SELECT `BelongsTo`, COUNT(*) FROM `Breezecard` WHERE `BelongsTo` = %s GROUP BY `BelongsTo`""", [prevOwner])

				# previous owner has at least one card
				cardCount = dbCursor.fetchall() # >= 1

			except:
				error = "Couldn't retrieve number of breezecards for previous owner"
				return render_template("suspended.html", suspendedList=suspendedList, error=error)

			cardInTrip = None 	# placeholder

			try:
				# check if this card is currently in a trip
				dbCursor.execute("""SELECT * FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [cardNumber])

				cardInTrip = dbCursor.rowcount 	# either 0 or 1 if not in trip or is

			except:
				error = "Couldn't see if card is currently in a trip at the moment"
				return render_template("suspended.html", suspendedList=suspendedList, error=error)

			if cardInTrip == 0: 	# card is not in trip - check count of user's breezecards

				# whether or not the user has 1 or more cards, both do the following procedure of updating card ownership and clearing conflicts
				try:
					# previous owner has more than one card and card is not in trip - assign card to new owner and reset value
					dbCursor.execute("""UPDATE `Breezecard`	SET `BelongsTo` = %s, Value = 0
										WHERE `BelongsTo` = %s AND `BreezecardNum` = %s""", [newOwner, prevOwner, cardNumber])

				except:
					error = "Couldn't transfer card at the moment"
					return render_template("suspended.html", suspendedList=suspendedList, error=error)

				db.commit()				# commit changes
				dbCursor.close()
				db.close()

				db = openDb()				# re-open database
				dbCursor = db.cursor()

				try:
					# resolve all conflicts
					dbCursor.execute("""DELETE FROM `Conflict` WHERE `BreezecardNum` = %s""", [cardNumber])

				except:
					error = "Couldn't assign card to new owner"
					return render_template("suspended.html", suspendedList=suspendedList, error=error)

				db.commit()				# commit changes
				dbCursor.close()
				db.close()

				db = openDb()				# re-open database
				dbCursor = db.cursor()


				# cardCount won't be None if gets here - exception would've been handled
				if cardCount[0][1] == 1: # user has only this card - extra functionality to give them a new one

					# give previous owner a newly generate breezecard
					generate_breezecard(dbCursor, prevOwner)

			else:	# card is in a trip
				error = "This card is currently in a trip. Can't reassign at the moment"
				return render_template("suspended.html", suspendedList=suspendedList, error=error)

		elif "bottom-button" in request.form: # keep card with previous owner - doesn't matter if card is in trip

			try:
				dbCursor.execute("""DELETE FROM `Conflict`
									WHERE `BreezecardNum` = %s""", [cardNumber])
				# remove all conflicts from table for breezecard number
				# card still BelongsTo previous owner

			except:
				error = "Couldn't assign card to previous owner"
				return render_template("suspended.html", suspendedList=suspendedList, error=error)

	db.commit()
	dbCursor.close()
	db.close()

	suspendedReturn = get_suspended_cards() # get updated suspended list

	if type(suspendedReturn) is str: # method returned an error message
		error = suspendedReturn
	else: # method return list of suspended cards
		suspendedList = suspendedReturn

	return render_template("suspended.html", suspendedList = suspendedList, error = error)

# WORKS
def get_pass_breezecards(username):

	breezecardList = []
	pass_breezecards = None # placeholder value

	db = openDb()
	dbCursor = db.cursor()

	try:

		# retrieve list of breezecards for logged in user that aren't suspended
		dbCursor.execute("""SELECT `BreezecardNum`, `Value`
							FROM `Breezecard`
							WHERE `BelongsTo` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)""", [username])

		pass_breezecards = dbCursor.fetchall() # gets tuples of breezecards from query

	except: # return "error" message

		return "Your list of active breezecards couldn't be loaded at this time"

	# if gets past exception handling, pass_breezecards will be a list (not None)

	for breezecard in pass_breezecards: # iterate through each breezecard
		breezecardRow = []
		count = 0
		for data in breezecard: # iterate through specific card's info
			if count == 0: # card number
				# add space between every four digits
				breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
			else:
				breezecardRow.append(data)
			count += 1
		breezecardList.append(breezecardRow)

	db.commit()
	dbCursor.close()
	db.close()

	return breezecardList # only hits if query was succesful

# WORKS
@app.route('/passenger_breezecards/<username>', methods=['POST', 'GET'])
def pass_breezecards(username):

	db = openDb()
	dbCursor = db.cursor()

	removeError = None
	tableNote = None
	addError = None
	addNote = None
	valueError = None

	breezecardList = None
	returnedValue = get_pass_breezecards(username)

	if type(returnedValue) is str: # list wasn't retrieved - error message was returned
		# breezecardList should be empty
		return render_template("passenger_breezecards.html", breezecardList=[], removeError=returnedValue, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)
	else: # list was returned
		if len(returnedValue) == 0 and request.method != "POST": # list is empty - no active breezecards *** AND *** not posting with add card or add value
			tableNote = "You have no active breezecards. Add one to your right"
			# breezecardList should be empty
			return render_template("passenger_breezecards.html", breezecardList=[], removeError=returnedValue, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)
		else:
			breezecardList = returnedValue

	# after this if/else statement, breezecardList will be a list or the method will have returned already

	if request.method == "POST": # clicking one of the three buttons

		if "removeCard" in request.form: # user clicks "Remove Selected Card"

			# user has not actually selected a card
			if "removed_breezecard" not in request.form:
				removeError = "Please select a breezecard to remove"
				return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

			# only gets here if breezecard has been selected (passes if statement)
			cardCount = None # placeholder value

			try:
				# retrieve count of breezecards for logged in user
				dbCursor.execute("""SELECT `BelongsTo`, COUNT(*) FROM `Breezecard` WHERE `BelongsTo` = %s GROUP BY `BelongsTo`""", [username])

				cardCount = dbCursor.fetchall() # tuple with username, number of breezecards

			except: # query fails for some reason

				removeError = "Unable to retrieve count of your breezecards at this moment"
				return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

			# only gets here if query passes (cardCount is no longer None)
			cardNumber = request.form['removed_breezecard'] # retrieve breezecard number from selected radio button
			cardNumber = cardNumber.replace(" ", "") # remove extra spaces

			if cardCount[0][1] > 1: # user has more than one breezecard

				cardInTrip = None # placeholder value

				try: # make sure breezecard being removed is not in a trip

					dbCursor.execute("""SELECT * FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [cardNumber])
					# find if selected breezecard is currently in a trip

					cardInTrip = dbCursor.rowcount # 0 or 1 for whether breezecard attached to ongoing trip

				except: # query fails for some reason
					removeError = "Couldn't retrieve trips associated with selected card at this moment"
					return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

				# if exception not raised, cardInTrip will have a value
				if cardInTrip > 0: # selected card is in a trip
					removeError = "Can't remove selected card. It's being used for a trip right now"
					return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

				else: # selected card is not in a trip currently

					try:
						# remove attachment to user, but keep card value???

						# dbCursor.execute("""UPDATE `Breezecard`
						# 					SET `Value` = 0, `BelongsTo` = NULL
						# 					WHERE `BreezecardNum` = %s""", [cardNumber])

						dbCursor.execute("""UPDATE `Breezecard`
											SET `BelongsTo` = NULL
											WHERE `BreezecardNum` = %s""", [cardNumber])

					except: # query fails for some reason
						removeError = "Couldn't remove selected breezecard"
						return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

			else: # user has only this breezecard
				removeError = "This is your only breezecard; can't delete it."
				return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

		elif "addCard" in request.form:

			cardNumber = request.form["addedCardNumber"]
			cardNumber = cardNumber.replace(" ", "") # remove extraneous spaces for inputted card number

			numberTuples = None # placeholder value

			try:
				# selects information for inputted breezecard number
				dbCursor.execute("""SELECT * FROM `Breezecard` WHERE `BreezecardNum` = %s""", [cardNumber])

				numberTuples = dbCursor.rowcount # breezecard number is key, so will return either 0 or 1 tuples of data
				retrievedBreezecard = dbCursor.fetchall()

			except:
				addError = "Unable to perform this action at the moment"
				return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

			# numberTuples will have a value - exception didn't happen
			if numberTuples > 0: # breezecard already exists in database

				if retrievedBreezecard[0][2] == None: # BelongsTo for breezecard is NULL
					# Breezecard has no user associated with it - give it to current user and reset value
					dbCursor.execute("""UPDATE `Breezecard` SET `BelongsTo` = %s WHERE `BreezecardNum` = %s""", [username, cardNumber])

				elif retrievedBreezecard[0][2] == username: # card already associated with current user
					addNote = "You already have this breezecard. Recheck table or it might be suspended"
					return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

				else: # breezecard already taken by another passenger

					dateTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

					try: # create Conflict (i.e. suspend card)

						dbCursor.execute("""INSERT INTO `Conflict`(`Username`, `BreezecardNum`, `DateTime`) VALUES (%s, %s, %s)""", [username, cardNumber, dateTime])

					except: # conflict already created for this user and breezecard

						addNote = "You've already tried to access this card before. It's been suspended"
						return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

					generate_breezecard(dbCursor, username) # generate new card for current user not already in database

					addNote = "Couldn't add requested card; new card has been created."
					# don't return here because we want to update database and get updated table

			else: # breezecard doesn't exist

				try:
					dbCursor.execute("""INSERT INTO `Breezecard`(`BreezecardNum`, `Value`, `BelongsTo`) VALUES (%s, 0, %s)""", [cardNumber, username])

				except:
					addError = "Unable to add card at this moment"
					return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

		elif "addValue" in request.form:

			breezecard = request.form["valueBreezecard"]
			breezecard = breezecard.replace(" ", "")
			value = request.form["value"]

			# placeholder values
			storedCardTuple = None
			breezecardTuples = None

			try: # get breezecard data for inputted card number and username if it's not suspended
				dbCursor.execute("""SELECT * FROM `Breezecard`
									WHERE `BreezecardNum` = %s AND `BelongsTo` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)""", [breezecard, username])

				breezecardTuples = dbCursor.rowcount # either 0 or 1
				storedCardTuple = dbCursor.fetchall() # tuple of breezecard meeting this criteria or empty tuple

			except: # handles cards that the user doesn't have or that are suspended for them
				valueError = "Couldn't perform this action at the moment"
				return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

			# exception doesn't happen so breezecardTuples has a value (not None)
			if breezecardTuples == 0: # handles 1) card is suspended, 2) card doesn't belong to user, 3) card doesn't exist

				valueError = "This isn't one of your active cards"
				return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

			else: # card exists for this user and is active

				storedCardValue = storedCardTuple[0][1] 	# value for breezecard
				total = int(value) + int(storedCardValue) 		# check if total will exceed limit of $1000.00

				if (total > 1000):

					valueError = "Breezecard values cannot exceed $1000.00"
					return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

				else:

					try:
						# give specified breezecard new value amount
						dbCursor.execute("""UPDATE `Breezecard` SET `Value` = %s WHERE `BreezecardNum` = %s""", [total, breezecard])

					except:
						valueError = "Couldn't update value of breezecard at the moment"
						return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)


	db.commit()
	dbCursor.close()
	db.close()

	breezecardList = get_pass_breezecards(username)
	# refresh list of breezecards in case of DB additions/removals

	return render_template("passenger_breezecards.html", breezecardList=breezecardList, removeError=removeError, addError=addError, valueError=valueError, username=username, tableNote=tableNote, addNote=addNote)

# WORKS
# get timestamp from 24-hour clock to a 12-hour clock
def get_timestamp(time):

	time = str(time)

	if time[11:13] < "12": # morning hours
		time = time[0:] + " AM"
	elif time[11:13] > "12": # afternoon/evening hours
		time = time[0:11] + str(int(time[11:13]) - 12) + time[13:] + " PM"
	else: # time is 12 o'clock noon hour
		time = time[0:] + " PM"

	if time[11:13] == "00": # time is 12 o'clock midnight hour
		time = time[0:11] + "12" + time[13:]

	return time

# WORKS
def get_trips(username):

	tripList = []

	db = openDb()
	dbCursor = db.cursor()

	breezecards = None

	try:
		# get all active breezecard numbers for username
		dbCursor.execute("""SELECT `BreezecardNum` FROM `Breezecard` WHERE `BelongsTo` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)""", [username])

		breezecards = dbCursor.fetchall() # tuples for breezecards

	except: # query fails for some reason

		return "Unable to get active breezecards for this user at the moment"

	# only reaches this point if exception doesn't occur - breezecards has value (even if empty)
	for card in breezecards:
		# search trips associated with each card associated with username

		trips = None # placeholder value

		try:
			# get trip tuples for specific active breezecard - only ended trips (no active ones)
			dbCursor.execute("""SELECT `StartTime`, `StartsAt`, `EndsAt`, `Tripfare`, `BreezecardNum` FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NOT NULL""", [card[0]])
			trips = dbCursor.fetchall()

		except:

			return "Couldn't get trips for breezecards at the moment"

		# only comes here if no exception - trips has value
		for trip in trips:
			tripRow = []
			count = 0
			for data in trip:
				if count == 0:
					timeStamp = get_timestamp(data) # get timestamp from 24-hour clock to 12-hour clock
					tripRow.append(timeStamp)
				elif count == 4: # give breezecard number extra spaces
					tripRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
				else:
					tripRow.append(data)
				count += 1
			tripList.append(tripRow)

	return tripList # will be empty list if trips or breezecards are empty

def convert_time(time):

	time = time.replace("T", " ")

	if len(time) == 16:
		time = time[0:] + ":00" # filter time was at %h:00:00

	return time

# WORKS
@app.route('/view_trips/<username>', methods=['POST','GET'])
def view_trips(username):

	filterError = None
	loadError = None
	note = None

	db = openDb()
	dbCursor = db.cursor()

	tripList = None
	returnedValue = get_trips(username)

	if type(returnedValue) is str: # list wasn't retrieved - error message was returned
		# tripList should be empty
		return render_template("view_trips.html", tripList = [], filterError=filterError, loadError=returnedValue, username=username, note=note)
	else: # list was returned
		if len(returnedValue) == 0 and request.method != "POST": # list is empty - no finished trips with active breezecards *** AND *** not posting filters
			note = "You have no finished trips for active breezecards"
			# tripList should be empty
			return render_template("view_trips.html", tripList = [], filterError=filterError, loadError=returnedValue, username=username, note=note)
		else: # non-empty list of trips
			tripList = returnedValue

	# filter or reset was clicked
	if request.method == "POST":

		db = openDb()
		dbCursor = db.cursor()

		if "update" in request.form: # filters are applied

			start = request.form["startTime"]
			end = request.form["endTime"]

			# make adjustments to passed in times to get them in correct format
			start = convert_time(start)
			end = convert_time(end)

			start = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
			end = datetime.datetime.strptime(end, "%Y-%m-%d %H:%M:%S")

			filtered = None # placeholder values
			filterCount = None

			try:
				# query database for trips associated with active breezecards for user that fall within time range and are not still in progress
				dbCursor.execute("""SELECT `StartTime`,`StartsAt`,`EndsAt`,`Tripfare`,`BreezecardNum` FROM Trip
									WHERE `BreezecardNum` IN (SELECT `BreezecardNum` FROM Breezecard WHERE `BelongsTo` = %s
									AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM Conflict)) AND `StartTime` >= %s
									AND `StartTime` <= %s AND `EndsAt` IS NOT NULL""", [username, start, end])

				filtered = dbCursor.fetchall() # tuples for trips meeting criteria
				filterCount = dbCursor.rowcount

			except: # query fails for some reason

				filterError = "Couldn't load trips based on filters at this moment"
				return render_template("view_trips.html", tripList = tripList, filterError=filterError, loadError=loadError, username=username, note=note)

			# only gets here if query was successful (filtered and filterCount have values)
			if filterCount == 0: # there are no trips meeting these filter criteria

				filterError = "None of your trips match this filter criteria. Reset or apply new filter"
				tripList = [] # clear tripList
				return render_template("view_trips.html", tripList = tripList, filterError=filterError, loadError=loadError, username=username, note=note)

			else:

				subTrips = []

				for trip in filtered:
					tripRow = []
					count = 0
					for data in trip:
						if count == 0:
							timeStamp = get_timestamp(data) # call method to get 12-hour clock time
							tripRow.append(timeStamp)
						elif count == 4: # add spaces to breezecard number
							tripRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						else:
							tripRow.append(data)
						count += 1
					subTrips.append(tripRow)

				tripList = subTrips

		elif "reset" in request.method: # reload table of trips to original list

			tripList = get_trips(username)


	db.commit()
	dbCursor.close()
	db.close()

	return render_template("view_trips.html", tripList = tripList, filterError=filterError, loadError=loadError, username=username, note=note)

# WORKS
def get_start_stations():

	stationList = []

	db = openDb()
	dbCursor = db.cursor()

	startStations = None # placeholder

	try:
		# get all stations
		dbCursor.execute("""SELECT * FROM `Station`""")

		startStations = dbCursor.fetchall()

	except:
		return "Couldn't get list of starting stations at the moment"


	# create table rows for station table - only get here if no exception (startStations has value)
	for station in startStations:
		openStatus = True
		stopID = station[0]
		stationRow = []
		count = 0

		for data in station:
			if count == 3:		# closed status

				if data == 0:
					stationRow.append("Open")

				else:
					openStatus = None
					stationRow.append("Closed")

			elif count == 4:	# type of station

				if data == 0: # not a Train station
					stationRow.append("Bus")
					intersection = None

					try:
						dbCursor.execute("""SELECT `Intersection` FROM `BusStationIntersection` WHERE `StopID` = %s""", [stopID])
						intersection = dbCursor.fetchall()[0][0]

					except:
						return "Couldn't get intersections for bus stations at the moment"

					if intersection == "" or intersection == None: # bus station has no intersection
						stationRow.append("---")

					else:
						stationRow.append(intersection)

				else:	# station type is train
					stationRow.append("Train")
					stationRow.append("---") # placeholder for intersection column

			else:
				stationRow.append(data)

			count += 1

		stationRow.append(openStatus)
		stationList.append(stationRow)

	db.commit()
	dbCursor.close()
	db.close()

	return stationList

# WORKS
def get_end_stations(username):

	stationList = []

	db = openDb()
	dbCursor = db.cursor()

	breezecards = None # placeholder

	try:

		dbCursor.execute("""SELECT `BreezecardNum` FROM `Breezecard` WHERE `BelongsTo` = %s""", [username])

		breezecards = dbCursor.fetchall()

	except:
		return "Couldn't get your breezecards at the moment"

	endTrip = False
	startStation = None
	isTrain = 0

	# only get here if no exception - breezecards has value
	for breezecard in breezecards:
		cardNum = breezecard[0]
		numberEmptyTrips = None # placeholder values
		trip = None

		try:
			# try to retrieve trip from Trips for breezecard from user that is in a trip
			dbCursor.execute("""SELECT `StartsAt`, `BreezecardNum` FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [cardNum])

			numberEmptyTrips = dbCursor.rowcount 	# 0 or 1 whether card has no trip/not in Trip or has ongoing trip
			trip = dbCursor.fetchall() 				# gets tuple for trip or is empty

		except:
			return "Couldn't get trips for breezecards at the moment"

		# only gets here if no exception
		if numberEmptyTrips > 0: 		# this breezecard has an ongoing trip
			tripCard = trip[0][1] 		# get card number from tuple
			startStation = trip[0][0]	# get ID for starting station
			endTrip = True				# we want to end the trip
			break						# break from loop


	if endTrip: # we found a card that has an ongoing trip

		endStations = None 			# placeholder value

		try:
			# get bus/train type for specific stopID
			dbCursor.execute("""SELECT `IsTrain` FROM `Station` WHERE `StopID` = %s""", [startStation])

			isTrain = dbCursor.fetchall()[0][0]

		except:
			return "Couldn't get status of starting station at the moment"

		try:
			# select all stations that have same bus/train status
			dbCursor.execute("""SELECT * FROM `Station` where `IsTrain` = %s""", [isTrain])

			endStations = dbCursor.fetchall() 	# store all potential end stations

		except:
			return "Couldn't get stations of same type as starting station"

		# only gets here if no exceptions - endStations has value
		for station in endStations:
			openStatus = True
			stopID = station[0]
			stationRow = []
			count = 0

			for data in station:
				if count == 3:	# closed status

					if data == 0:
						stationRow.append("Open")
					else:
						openStatus = None
						stationRow.append("Closed")

				elif count == 4:	# type of station

					if data == 0: # not a Train station
						stationRow.append("Bus")
						intersection = None # placeholder value

						try:
							# get intersection for this bus station
							dbCursor.execute("""SELECT `Intersection` FROM `BusStationIntersection` WHERE `StopID` = %s""", [stopID])
							intersection = dbCursor.fetchall()[0][0]

						except:
							return "Couldn't get intersections of bus stations at the moment"

						# only gets here if no exception - intersection has value
						if intersection == "" or intersection == None: # bus station has no intersection
							stationRow.append("---")
						else: # bus station has intersection
							stationRow.append(intersection)

					else: # is a Train station
						stationRow.append("Train")
						stationRow.append("---") # placeholder for intersection column

				else:
					stationRow.append(data)

				count += 1

			stationRow.append(openStatus) # lets frontend know if to disable select button or not
			stationList.append(stationRow)

	db.commit()
	dbCursor.close()
	db.close()

	return stationList

# WORKS
@app.route('/pass_trips/<username>', methods=['POST','GET'])
def take_trip(username):

	stationList = []
	validBreezecards = []

	error = None
	tableNote = None

	db = openDb()
	dbCursor = db.cursor()

	breezecards = None # placeholder value

	try:
		# select all breezecards for username - even suspended ones (card can be suspended and have a trip if suspension happens during trip)
		dbCursor.execute("""SELECT `BreezecardNum` FROM `Breezecard` WHERE `BelongsTo` = %s""", [username])

		breezecards = dbCursor.fetchall()

	except:
		error = "Couldn't load breezecards for user at the moment"
		return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)


	# only gets here if no exception - breezecards has value
	endTrip = False 		# default "user is starting trip"
	startStation = None		# placeholder values
	isTrain = 0
	tripCard = None			# holds card number for card in trip
	showEndStations = None

	for breezecard in breezecards: # iterate through each user breezecard
		cardNum = breezecard[0]

		numberEmptyTrips = None # placeholder values
		trip = None

		try:
			# try to retrieve trip from Trips for breezecard from user that is in a trip
			dbCursor.execute("""SELECT `StartsAt`, `BreezecardNum` FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [cardNum])

			numberEmptyTrips = dbCursor.rowcount 	# 0 or 1 whether card has no trip/not in Trip or has ongoing trip
			trip = dbCursor.fetchall() 				# gets tuple for trip or is empty

		except:
			error = "Couldn't get trips for breezecards at the moment"
			return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

		# only gets here if no exception
		if numberEmptyTrips > 0: 		# this breezecard has an ongoing trip
			tripCard = trip[0][1] 		# get card number from tuple
			startStation = trip[0][0]	# get ID for starting station
			endTrip = True				# we want to end the trip
			break						# break from loop


	if endTrip: # we found a card that has an ongoing trip

		showEndStations = True		# condition for front end to show end stations
		endStations = None 			# placeholder value

		try:
			# get bus/train type for specific stopID
			dbCursor.execute("""SELECT `IsTrain` FROM `Station` WHERE `StopID` = %s""", [startStation])

			isTrain = dbCursor.fetchall()[0][0]

		except:
			error = "Couldn't get status of starting station at the moment"
			return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

		try:
			# select all stations that have same bus/train status
			dbCursor.execute("""SELECT * FROM `Station` where `IsTrain` = %s""", [isTrain])

			endStations = dbCursor.fetchall() 	# store all potential end stations

		except:
			error = "Couldn't get stations of same type as starting station"
			return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

		# only gets here if no exceptions - endStations has value
		for station in endStations:
			openStatus = True
			stopID = station[0]
			stationRow = []
			count = 0

			for data in station:
				if count == 3:	# closed status

					if data == 0:
						stationRow.append("Open")
					else:
						openStatus = None
						stationRow.append("Closed")

				elif count == 4:	# type of station

					if data == 0: # not a Train station
						stationRow.append("Bus")
						intersection = None # placeholder value

						try:
							# get intersection for this bus station
							dbCursor.execute("""SELECT `Intersection` FROM `BusStationIntersection` WHERE `StopID` = %s""", [stopID])
							intersection = dbCursor.fetchall()[0][0]

						except:
							error = "Couldn't get intersections of bus stations at the moment"
							return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

						# only gets here if no exception - intersection has value
						if intersection == "" or intersection == None: # bus station has no intersection
							stationRow.append("---")
						else: # bus station has intersection
							stationRow.append(intersection)

					else: # is a Train station
						stationRow.append("Train")
						stationRow.append("---") # placeholder for intersection column

				else:
					stationRow.append(data)

				count += 1

			stationRow.append(openStatus) # lets frontend know if to disable select button or not
			stationList.append(stationRow)


	else: # no breezecard with ongoing trip

		showEndStations = None	# want starting stations
		startStations = None	# placeholder value

		try:
			# get all stations
			dbCursor.execute("""SELECT * FROM `Station`""")

			startStations = dbCursor.fetchall()

		except:
			error = "Couldn't get stations at the moment"
			return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)


		# only gets here if no exception - startStations has value
		# create table rows for station table
		for station in startStations:
			openStatus = True
			stopID = station[0]
			stationRow = []
			count = 0

			for data in station:
				if count == 3:	# closed status

					if data == 0:
						stationRow.append("Open")
					else:
						openStatus = None
						stationRow.append("Closed")

				elif count == 4:	# type of station

					if data == 0: # not a Train station
						stationRow.append("Bus")
						intersection = None # placeholder value

						try:
							# get intersection for this bus station
							dbCursor.execute("""SELECT `Intersection` FROM `BusStationIntersection` WHERE `StopID` = %s""", [stopID])
							intersection = dbCursor.fetchall()[0][0]

						except:
							error = "Couldn't get intersections of bus stations at the moment"
							return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

						# only gets here if no exception - intersection has value
						if intersection == "" or intersection == None: # bus station has no intersection
							stationRow.append("---")
						else: # bus station has intersection
							stationRow.append(intersection)

					else: # is a Train station
						stationRow.append("Train")
						stationRow.append("---") # placeholder for intersection column

				else:
					stationRow.append(data)

				count += 1

			stationRow.append(openStatus) # lets frontend know if to disable select button or not
			stationList.append(stationRow)


		cardCount = None 			# placeholder values
		activeBreezecards = None

		try:
			# get active breezecards for this username
			dbCursor.execute("""SELECT `BreezecardNum`, `Value` FROM `Breezecard`
								WHERE `BelongsTo` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)""", [username])
								# get all ACTIVE breezecards

			count = dbCursor.rowcount
			activeBreezecards = dbCursor.fetchall()

		except:
			error = "Couldn't get active breezecards at the moment"
			return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)


		# only gets here if no exception - cardCount and activeBreezecards have value
		if count > 0: # user has some active breezecards

			for active in activeBreezecards:
				breezecardRow = []
				count = 0
				for data in active:
					if count == 0:	# add spaces to breezecard number
						breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
					else:
						breezecardRow.append(data)
					count += 1
				validBreezecards.append(breezecardRow)

		else:
			error = "You have no active cards. You can't take a trip"
			return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)



	if request.method == "POST": # start trip or end trip is selected

		if "startTrip" in request.form: # user is starting a trip

			# neither station nor breezecard is selected
			if "selected_station" not in request.form and "selected_breezecard" not in request.form:
				error = "Please select a starting station and a breezecard"
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

			# only station is not selected
			elif "selected_station" not in request.form:
				error = "Please select a station to be your start point."
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

			# only breezecard is not selected
			elif "selected_breezecard" not in request.form:
				error = "Please select a breezecard to pay for this trip."
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

			# both station and breezecard are chosen

			station = request.form["selected_station"] # holds stop ID and enter fare
			station = station.split(",")
			stationSubList = []
			for value in station:
				value = value.replace("'", "")
				value = value.replace(" ", "")
				value = value.replace("(", "")
				value = value.replace(")", "")
				stationSubList.append(value)

			# extracts data from this passed in string from the form

			stationID = stationSubList[0]
			enterFare = Decimal(stationSubList[1].replace("Decimal", ""))

			breezecard = request.form["selected_breezecard"] # holds breezecard number and card value
			breezecard = breezecard.split(",")
			cardSubList = []
			for value in breezecard:
				value = value.replace("'", "")
				value = value.replace(" ", "")
				value = value.replace("(", "")
				value = value.replace(")", "")
				cardSubList.append(value)

			# extracts data from this passed in string from the form

			cardNumber = cardSubList[0]
			cardValue = Decimal(cardSubList[1].replace("Decimal", ""))

			if cardValue >= enterFare: # card has enough money to pay for trip

				newCardValue = cardValue - enterFare
				newCardValue = str(newCardValue)

				try:
					# update breezecard value to new card value
					dbCursor.execute("""UPDATE `Breezecard` SET `Value` = %s WHERE `BreezecardNum` = %s""", [newCardValue, cardNumber])

					db.commit() 			# commit changes
					dbCursor.close()
					db.close()

				except:
					error = "Couldn't pay for fare at the moment. Can't take trip"
					return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

				tripStartTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

				db = openDb()
				dbCursor = db.cursor()

				try:
					# inseert new instance of trip into database - unlikely that it fails unless time and breezecard are EXACTLY the same as another instance
					dbCursor.execute("""INSERT INTO `Trip`(`Tripfare`, `StartTime`, `BreezecardNum`, `StartsAt`, `EndsAt`)
										VALUES (%s, %s, %s, %s, NULL)""", [enterFare, tripStartTime, cardNumber, stationID])

					db.commit() 			# commit changes
					dbCursor.close()
					db.close()

				except: # off-chance query does fail, just return and let them try again
					error = "Couldn't start trip at the moment. Try again"
					return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

				db = openDb()
				dbCursor = db.cursor()

				# only get here if no exceptions
				showEndStations = True
				validBreezecards = []		# clear validBreezecards list

				endStationReturn = get_end_stations(username)
				if type(endStationReturn) is str: # list wasn't retrieved - error message was returned
					# stationList should be empty
					return render_template("take_trip.html", error=endStationReturn, stationList=[], showEndStations=showEndStations, validBreezecards=[], username=username, tableNote=tableNote)
				else: # list was returned
					if len(endStationReturn) == 0: # list is empty - no stations to load (SHOULD NOT HAPPEN EVER - STATIONS SHOULD NOT BE DELETED)
						error = "There are no stations to travel to"
						# stationList should be empty
						return render_template("take_trip.html", error=error, stationList=[], showEndStations=showEndStations, validBreezecards=[], username=username, tableNote=tableNote)
					else:
						stationList = endStationReturn


				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

			else:
				error = "This card doesn't have enough funds to take this trip."
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)


		elif "endTrip" in request.form: # user is ending a trip

			if "selected_station" not in request.form: # didn't select a station to end at
				error = "Please select a station to be your ending point."
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)


			stationID = request.form["selected_station"]

			removeTuple = None # placeholder

			try:
				# get tuple for breezecard in ongoing trip
				# tripCard will have a value - updated by code before POST check
				dbCursor.execute("""SELECT * FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [tripCard])

				removeTuple = dbCursor.fetchall()[0] # only going to be one tuple - trying to end trip so we know one exists

			except:
				error = "Couldn't get information for current trip"
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)


			# removeTuple will have a value here - exception didn't happen
			try:

				# delete ongoing trip tuple
				dbCursor.execute("""DELETE FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [tripCard])

			except:
				error = "Couldn't end your current trip at the moment. Try again"
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

			db.commit()				# commit those changes
			dbCursor.close()
			db.close()

			db = openDb()				# re-open database
			dbCursor = db.cursor()

			try:
				# re-insert tuple data to avoid timestamp update with mysql - add in selected end station
				dbCursor.execute("""INSERT INTO `Trip`(`Tripfare`, `StartTime`, `BreezecardNum`, `StartsAt`, `EndsAt`)
									VALUES (%s, %s, %s, %s, %s)""", [removeTuple[0], removeTuple[1], removeTuple[2], removeTuple[3], stationID])

			except:
				error = "Couldn't end your current trip at the moment. Try again"
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=validBreezecards, username=username, tableNote=tableNote)

			db.commit()				# commit those changes
			dbCursor.close()
			db.close()

			db = openDb()				# re-open database
			dbCursor = db.cursor()

			# only happens if not exception
			showEndStations = None					# reset so starting stations will now be shown

			stationReturn = get_start_stations() # get list of starting stations
			if type(stationReturn) is str: # list wasn't retrieved - error message was returned
				# stationList and validBreezecards should be empty
				return render_template("take_trip.html", error=breezecardReturn, stationList=[], showEndStations=showEndStations, validBreezecards=[], username=username, tableNote=tableNote)
			else: # list was returned
				if len(stationReturn) == 0: # list is empty - no stations to load (SHOULD NOT HAPPEN EVER - STATIONS SHOULD NOT BE DELETED)
					error = "There are no stations to travel from"
					# stationList and validBreezecards hould be empty
					return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=[], validBreezecards=[], username=username, tableNote=tableNote)
				else:
					stationList = stationReturn

			# will only occur if stationList assignment works
			breezecardReturn = get_pass_breezecards(username)
			if type(breezecardReturn) is str: # list wasn't retrieved - error message was returned
				# validBreezecards should be empty
				return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=[], username=username, tableNote=breezecardReturn)
			else: # list was returned
				if len(breezecardReturn) == 0: # list is empty - no active breezecards to load
					tableNote = "You have no active breezecards. You can't take a trip"
					# validBreezecards should be empty
					return render_template("take_trip.html", error=error, stationList=stationList, showEndStations=showEndStations, validBreezecards=[], username=username, tableNote=tableNote)
				else:
					validBreezecards = breezecardReturn

			error = None


	db.commit()
	dbCursor.close()
	db.close()

	# stationList = get_end_stations(username)

	return render_template("take_trip.html", error=error, stationList=stationList, username=username, showEndStations=showEndStations, validBreezecards=validBreezecards, tableNote=tableNote)

# WORKS
def get_reports():

	flowList = []

	db = openDb()
	dbCursor = db.cursor()

	flowReports = None # placeholder value

	try:

		# get result table from left outer joining Station, Trip, and Trip (flow report columns)
		dbCursor.execute("""SELECT SN.`StopID`, SN.`Name`, IFNULL(ST.`PassIn`,0) AS `PassIn`, IFNULL(ET.`PassOut`,0) AS `PassOut`, (IFNULL(`PassIn`,0) - IFNULL(`PassOut`,0)) AS `Flow`, IFNULL(ST.`SumFare`,0) AS `Revenue`, SN.`IsTrain`
							FROM (SELECT A.`StopID`, A.`Name`, A.`IsTrain` FROM Station AS A) AS `SN`
							LEFT OUTER JOIN (SELECT B.`StartsAt`,SUM(B.`Tripfare`) AS `SumFare`,COUNT(*) AS `PassIn` FROM Trip AS B GROUP BY B.`StartsAt`) AS `ST`
							ON SN.`StopID` = ST.`StartsAt`
							LEFT OUTER JOIN (SELECT C.`EndsAt`,COUNT(*) AS `PassOut` FROM Trip AS C WHERE C.`EndsAt` IS NOT NULL GROUP BY C.`EndsAt`) AS `ET`
							ON SN.`StopID` = ET.`EndsAt` ORDER BY `PassIn` DESC, `PassOut` DESC""")

		flowReports = dbCursor.fetchall()

	except:

		return "Couldn't load flow reports at the moment"

	# only reaches this point if exception didn't happen - flowReports has value
	for report in flowReports:
		flowRow = []
		count = 0

		for data in report:
			if count == 0 or count == 6:
				pass # don't want StopID or isTrain column to show in frontend
			elif count == 1:
				if report[6] == 0: # is a bus station
					flowRow.append(data + " - Bus")
				else: # is a train station
					flowRow.append(data + " - Train")
			else:
				flowRow.append(data)
			count += 1

		flowList.append(flowRow)


	db.commit()
	dbCursor.close()
	db.close()

	return flowList

# WORKS
@app.route('/flow_report', methods=['POST', 'GET'])
def flow_report():

	loadError = None
	filterError = None

	db = openDb()
	dbCursor = db.cursor()

	flowList = []
	returnedValue = get_reports()

	if type(returnedValue) is str: # list wasn't retrieved - error message was returned
		# flowList should be empty
		return render_template("flow_report.html", flowList=[], filterError=filterError, loadError=returnedValue)
	else: # list was returned
		# this case shouldn't happen - should always show flows even if 0 passengers
		if len(returnedValue) == 0 and request.method != "POST": # list is empty - no flow reports AND not posting filters
			loadError = "There are no flow reports to be loaded"
			# flowList should be empty
			return render_template("flow_report.html", flowList=[], filterError=filterError, loadError=loadError)
		else:
			flowList = returnedValue

	# filters are being applied
	if request.method == "POST":

		if "update" in request.form:

			start = request.form["startTime"]
			end = request.form["endTime"]

			if start == "" and end == "": # neither filter is applied - get all flow reports
				flowList = get_reports()

			elif end == "": # only start time filter is applied
				start = convert_time(start)
				start = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M:%S") # convert start time to appropriate format

				startFiltered = None # placeholders
				filterCount = None

				try:
					# get passengers in, out, flow, and revenue for each station within lower bounded time interval
					dbCursor.execute("""SELECT SN.`StopID`, SN.`Name`, IFNULL(ST.`PassIn`, 0 ) AS `PassIn`, IFNULL(ET.`PassOut`, 0) AS `PassOut` , (IFNULL(`PassIn`, 0 ) - IFNULL(`PassOut`, 0)) AS  `Flow`, IFNULL(ST.`SumFare`, 0 ) AS `Revenue`, SN.`IsTrain`
										FROM (SELECT A.`StopID`, A.`Name`, A.`IsTrain` FROM Station AS A) AS `SN`
										LEFT OUTER JOIN (
										SELECT B.`StartsAt` , SUM( B.`Tripfare` ) AS  `SumFare` , COUNT( * ) AS  `PassIn` FROM Trip AS B WHERE  `StartTime` >=  %s GROUP BY B.`StartsAt`) AS  `ST`
										ON SN.`StopID` = ST.`StartsAt`
										LEFT OUTER JOIN (
										SELECT C.`EndsAt` , COUNT( * ) AS  `PassOut` FROM Trip AS C WHERE C.`EndsAt` IS NOT NULL AND  `StartTime` >= %s GROUP BY C.`EndsAt`) AS  `ET`
										ON SN.`StopID` = ET.`EndsAt`
										ORDER BY  `PassIn` DESC,  `PassOut` DESC""", [start, start])

					startFiltered = dbCursor.fetchall()
					filterCount = dbCursor.rowcount

				except: # query fails for some reason

					filterError = "Couldn't filter by start time at the moment"
					return render_template("flow_report.html", flowList=flowList, filterError=filterError, loadError=loadError)

				# only reaches here if no exception - startFiltered and filterCount have values
				if filterCount == 0: # should never hit this case
					filterError = "There are no flow reports for this filter. Reset or apply new filter"
					# show empty flowList
					return render_template("flow_report.html", flowList=[], filterError=filterError, loadError=loadError)

				else: # should alwys hit this case

					subReports = []
					for report in startFiltered:
						flowRow = []
						count = 0
						for data in report:
							if count == 0 or count == 6:
								pass # don't want StopID or isTrain column
							elif count == 1:
								if report[6] == 0: # is a bus station
									flowRow.append(data + " - Bus")
								else: # is a train station
									flowRow.append(data + " - Train")
							else:
								flowRow.append(data)
							count += 1
						subReports.append(flowRow)

					flowList = subReports


			elif start == "": # only end time filter is applied

				end = convert_time(end)
				end = datetime.datetime.strptime(end, "%Y-%m-%d %H:%M:%S") # convert end time to appropriate format

				endFiltered = None # placeholders
				filterCount = None

				try:
					# get passengers in, out, flow, and revenue for each station within upper bounded time interval
					dbCursor.execute("""SELECT SN.`StopID`, SN.`Name`, IFNULL(ST.`PassIn`, 0 ) AS `PassIn`, IFNULL(ET.`PassOut`, 0) AS `PassOut` , (IFNULL(`PassIn`, 0 ) - IFNULL(`PassOut`, 0)) AS  `Flow`, IFNULL(ST.`SumFare`, 0 ) AS `Revenue`, SN.`IsTrain`
										FROM (SELECT A.`StopID`, A.`Name`, A.`IsTrain` FROM Station AS A) AS `SN`
										LEFT OUTER JOIN (
										SELECT B.`StartsAt` , SUM( B.`Tripfare` ) AS  `SumFare` , COUNT( * ) AS  `PassIn` FROM Trip AS B WHERE  `StartTime` <=  %s GROUP BY B.`StartsAt`) AS  `ST`
										ON SN.`StopID` = ST.`StartsAt`
										LEFT OUTER JOIN (
										SELECT C.`EndsAt` , COUNT( * ) AS  `PassOut` FROM Trip AS C WHERE C.`EndsAt` IS NOT NULL AND  `StartTime` <= %s GROUP BY C.`EndsAt`) AS  `ET`
										ON SN.`StopID` = ET.`EndsAt`
										ORDER BY  `PassIn` DESC,  `PassOut` DESC""", [end, end])

					endFiltered = dbCursor.fetchall()
					filterCount = dbCursor.rowcount

				except: # query fails for some reason

					filterError = "Couldn't filter by end time at the moment"
					return render_template("flow_report.html", flowList=flowList, filterError=filterError, loadError=loadError)

				# only reaches here if no exception - startFiltered and filterCount have values
				if filterCount == 0: # should never hit this case
					filterError = "There are no flow reports for this filter. Reset or apply new filter"
					# show empty flowList
					return render_template("flow_report.html", flowList=[], filterError=filterError, loadError=loadError)

				else: # should alwys hit this case

					subReports = []
					for report in endFiltered:
						flowRow = []
						count = 0
						for data in report:
							if count == 0 or count == 6:
								pass # don't want StopID or isTrain column
							elif count == 1:
								if report[6] == 0: # is a bus station
									flowRow.append(data + " - Bus")
								else: # is a train station
									flowRow.append(data + " - Train")
							else:
								flowRow.append(data)
							count += 1
						subReports.append(flowRow)

					flowList = subReports

			else: # both time filters are applie

				start = convert_time(start)
				end = convert_time(end)
				start = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
				end = datetime.datetime.strptime(end, "%Y-%m-%d %H:%M:%S") 			# convert times to correct format

				filtered = None # placeholders
				filterCount = None

				try:
					# get passengers in, out, flow, and revenue for each station within two sided time interval
					dbCursor.execute("""SELECT SN.`StopID`, SN.`Name`, IFNULL(ST.`PassIn`, 0 ) AS `PassIn`, IFNULL(ET.`PassOut`, 0) AS `PassOut` , (IFNULL(`PassIn`, 0 ) - IFNULL(`PassOut`, 0)) AS  `Flow`, IFNULL(ST.`SumFare`, 0 ) AS `Revenue`, SN.`IsTrain`
										FROM (SELECT A.`StopID`, A.`Name`, A.`IsTrain` FROM Station AS A) AS `SN`
										LEFT OUTER JOIN (
										SELECT B.`StartsAt` , SUM( B.`Tripfare` ) AS  `SumFare` , COUNT( * ) AS  `PassIn` FROM Trip AS B WHERE  `StartTime` >=  %s AND  `StartTime` <= %s GROUP BY B.`StartsAt`) AS  `ST`
										ON SN.`StopID` = ST.`StartsAt`
										LEFT OUTER JOIN (
										SELECT C.`EndsAt` , COUNT( * ) AS  `PassOut` FROM Trip AS C WHERE C.`EndsAt` IS NOT NULL AND  `StartTime` >= %s AND  `StartTime` <= %s GROUP BY C.`EndsAt`) AS  `ET`
										ON SN.`StopID` = ET.`EndsAt`
										ORDER BY  `PassIn` DESC,  `PassOut` DESC""", [start, end, start, end])

					filtered = dbCursor.fetchall()
					filterCount = dbCursor.rowcount

				except: # query fails for some reason

					filterError = "Couldn't filter by start and end time at the moment"
					return render_template("flow_report.html", flowList=flowList, filterError=filterError, loadError=loadError)


				# only reaches here if no exception - startFiltered and filterCount have values
				if filterCount == 0: # should never hit this case
					filterError = "There are no flow reports for this filter. Reset or apply new filter"
					# show empty flowList
					return render_template("flow_report.html", flowList=[], filterError=filterError, loadError=loadError)

				else: # should always hit this case

					subReports = []
					for report in filtered:
						flowRow = []
						count = 0
						for data in report:
							if count == 0 or count == 6:
								pass # don't want StopID or isTrain column
							elif count == 1:
								if report[6] == 0: # is a bus station
									flowRow.append(data + " - Bus")
								else: # is a train station
									flowRow.append(data + " - Train")
							else:
								flowRow.append(data)
							count += 1
						subReports.append(flowRow)
					flowList = subReports

		elif "reset" in request.method: # reset table of flow reports to original list

			flowList = get_reports()


	db.commit()
	dbCursor.close()
	db.close()

	return render_template("flow_report.html", flowList=flowList, filterError=filterError, loadError=loadError)

# get all breezecards that are not suspended
def get_all_breezecards():

	breezecardList = []

	db = openDb()
	dbCursor = db.cursor()

	breezecards = None # placeholder value

	try:
		# show all breezecards besides suspended ones
		dbCursor.execute("""SELECT * FROM `Breezecard` WHERE `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
							GROUP BY `BreezecardNum` ORDER BY `BreezecardNum` ASC""")

		breezecards = dbCursor.fetchall()

	except:

		return "Couldn't load all active breezecards at the moment"

	# only hits this if no exception - breezecards has values
	for breezecard in breezecards:
		breezecardRow = []
		count = 0
		for data in breezecard:
			if count == 0:
				# add spaces to breezecard number
				breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
			elif count == 2 and data == None:
				# belongsTo column is null - set owner column value to ---
				breezecardRow.append("---")
			else:
				breezecardRow.append(data)
			count += 1

		breezecardList.append(breezecardRow)

	return breezecardList

# WORKS
@app.route('/admin_breezecards/', methods=['POST', 'GET'])
def admin_breezecards():

	filterError = None
	filterNote = None
	loadError = None
	loadNote = None
	valueError = None
	transferError = None

	breezecardList = []
	returnedValue = get_all_breezecards() # gets all breezecards that are not suspended

	if type(returnedValue) is str: # list wasn't retrieved - error message was returned
		# breezecardList should be empty
		return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=returnedValue, loadNote=loadNote, filterNote=filterNote)
	else: # list was returned
		if len(returnedValue) == 0 and request.method != "POST": # list is empty - no active breezecards *** AND *** not posting with add card or add value
			loadNote = "You have no active breezecards. Add one to your right"
			# breezecardList should be empty
			return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)
		else: # actual list is returned
			breezecardList = returnedValue

	db = openDb()
	dbCursor = db.cursor()

	# filters applied OR transfer card applied OR set value applied
	if request.method == "POST":

		if "update" in request.form: # filters applied

			# no filters applied - give all active breezecards - WORKS
			if request.form["searchOwner"] == "" and request.form["searchCard"] == "" and request.form["bottomValue"] == "" and "showSuspended" not in request.form:

				filterError = "No filter(s) were applied."

			# only showSuspendedCards filter is applied - WORKS
			elif request.form["searchOwner"] == "" and request.form["searchCard"] == "" and request.form["bottomValue"] == "":

				numTuples = None
				breezecards = None

				try:
					# show all breezecards
					dbCursor.execute("""SELECT * FROM `Breezecard` GROUP BY `BreezecardNum` ORDER BY `BreezecardNum` ASC""")

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get all breezecards at the moment"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no suspended cards
					filterError = "There are no suspended cards"
					# show original list of just active breezecards
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							suspendedCard = None

							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount

							except:
								filterError = "Couldn't get suspended breezecards at the moment"
								return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

							if (suspendedCard > 0):
								suspended = True

							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))

						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# only search by card value is applied - WORKS
			elif request.form["searchOwner"] == "" and request.form["searchCard"] == "" and "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:
					# all breezecards within value range and not suspended
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `Value` >= %s AND `Value` <= %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [lowerValue, upperValue])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecards within value range"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)


				if numTuples == 0: # no cards in value range
					filterError = "There are no breezecards meeting this criteria or they're suspended. Click reset or enter new criteria."
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					count = 0
					for data in breezecard:
						if count == 0:
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with Null in BelongsTo
								breezecardRow.append("---")
							else:
								breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# only search by card number is applied - WORKS
			elif request.form["searchOwner"] == "" and request.form["bottomValue"] == "" and "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")

				try:
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BreezecardNum` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [cardNumber])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with specified number"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)


				if numTuples == 0: # no breezecard with this number
					filterError = "There is no breezecard with this number or it's suspended. Click reset or enter new criteria."
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					count = 0
					for data in breezecard:
						if count == 0:
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with Null in BelongsTo
								breezecardRow.append("---")
							else:
								breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# only search by owner is applied - WORKS
			elif request.form["searchCard"] == "" and request.form["bottomValue"] == "" and "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				owner = request.form["searchOwner"]

				try:
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BelongsTo` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [owner])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecards with specified owner"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecards for this owner
					filterError = "This user has only suspended cards - no active cards. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					count = 0
					for data in breezecard:
						if count == 0:
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						else:
							breezecardRow.append(data)
							# data for owner will never be NULL when searching card by username
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by value and suspended are chosen - WORKS
			elif request.form["searchOwner"] == "" and request.form["searchCard"] == "":

				numTuples = None
				breezecards = None
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `Value` >= %s AND `Value` <= %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [lowerValue, upperValue])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get suspended cards within value range"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecards within this value range
					filterError = "There are no breezecards meeting this criteria; click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by card and suspended are chosen - WORKS
			elif request.form["searchOwner"] == "" and request.form["bottomValue"] == "":

				numTuples = None
				breezecards = None
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BreezecardNum` = %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [cardNumber])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get suspended breezecard with specified number"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecards with this number
					filterError = "There are no breezecards meeting this criteria; click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by owner and suspended are chosen - WORKS
			elif request.form["searchCard"] == "" and request.form["bottomValue"] == "":

				numTuples = None
				breezecards = None
				owner = request.form["searchOwner"]

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BelongsTo` = %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [owner])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get suspended breezecard(s) with specified owner"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)


				if numTuples == 0: # no cards with this owner
					filterError = "There are no breezecards meeting this criteria; click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							# a card searched for by name will never be one with NULL in belongsTo
							if (suspended):
								breezecardRow.append("*** Suspended ***")
							else:
								breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by card and owner are applied - WORKS
			elif request.form["bottomValue"] == "" and "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				owner = request.form["searchOwner"]
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")

				try:
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BreezecardNum` = %s AND `BelongsTo` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [cardNumber, owner])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with number and owner"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecards with this number and owner
					filterError = "There are no breezecards meeting this criteria or they're suspended. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					count = 0
					for data in breezecard:
						if count == 0:
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						else:
							breezecardRow.append(data)
							# data for username will always be equal to inputted username
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by card and value are applied - WORKS
			elif request.form["searchOwner"] == "" and "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:

					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BreezecardNum` = %s AND `Value` >= %s AND `Value` <= %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [cardNumber, lowerValue, upperValue])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with number and within value range"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)


				if numTuples == 0: # no cards with this number and within value
					filterError = "There are no breezecards meeting this criteria or they're suspended. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by owner and value are applied - WORKS
			elif request.form["searchCard"] == "" and "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				owner = request.form["searchOwner"]
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BelongsTo` = %s AND `Value` >= %s AND `Value` <= %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [owner, lowerValue, upperValue])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with owner and within value range"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecards with owner and within value range
					filterError = "There are no breezecards meeting this criteria or they're suspended. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					count = 0
					for data in breezecard:
						if count == 0:
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						else:
							breezecardRow.append(data)
							# data for owner will never be NULL when searching for card by username
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by card, name, and suspended are applied - WORKS
			elif request.form["bottomValue"] == "":

				numTuples = None
				breezecards = None
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")
				owner = request.form["searchOwner"]

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BelongsTo` = %s AND `BreezecardNum` = %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [owner, cardNumber])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecards with number and owner"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecard with this owner and number
					filterError = "There are no breezecards meeting this criteria. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by card, name, and value are applied - WORKS
			elif "showSuspended" not in request.form:

				numTuples = None
				breezecards = None
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")
				owner = request.form["searchOwner"]
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:

					dbCursor.execute("""SELECT *
									FROM `Breezecard`
									WHERE `BelongsTo` = %s AND `Value` >= %s AND `Value` <= %s AND `BreezecardNum` = %s AND `BreezecardNum` NOT IN (SELECT DISTINCT `BreezecardNum` FROM `Conflict`)
									GROUP BY `BreezecardNum`
									ORDER BY `BreezecardNum` ASC""", [owner, lowerValue, upperValue, cardNumber])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with number, name, and within value"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no card with owner, number, and within value range
					filterError = "There are no breezecards meeting this criteria or they're suspended. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					count = 0
					for data in breezecard:
						if count == 0:
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						else:
							breezecardRow.append(data)
							# data for owner will never be NULL when searching for card by username
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# search by card, value, and suspended are applied - WORKS
			elif request.form["searchOwner"] == "":

				numTuples = None
				breezecards = None
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `BreezecardNum` = %s AND `Value` >= %s AND `Value` <= %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [cardNumber, lowerValue, upperValue])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with number and in value range"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecards with number and within value range
					filterError = "There are no breezecards meeting this criteria. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			#search by name, value, and suspended - WORKS
			elif request.form["searchCard"] == "":

				numTuples = None
				breezecards = None
				owner = request.form["searchOwner"]
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `Value` >= %s AND `Value` <= %s AND `BelongsTo` = %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [lowerValue, upperValue, owner])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with owner and within value"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no breezecard with this owner and within this value range
					filterError = "There are no breezecards meeting this criteria. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# all filters applied
			else:

				numTuples = None
				breezecards = None
				owner = request.form["searchOwner"]
				cardNumber = request.form["searchCard"]
				cardNumber = cardNumber.replace(" ", "")
				lowerValue = request.form["bottomValue"]
				upperValue = request.form["topValue"]

				try:
					# show all breezecards within value range
					dbCursor.execute("""SELECT *
										FROM `Breezecard`
										WHERE `Value` >= %s AND `Value` <= %s AND `BelongsTo` = %s AND `BreezecardNum` = %s
										GROUP BY `BreezecardNum`
										ORDER BY `BreezecardNum` ASC""", [lowerValue, upperValue, owner, cardNumber])

					numTuples = dbCursor.rowcount
					breezecards = dbCursor.fetchall()

				except:
					filterError = "Couldn't get breezecard with all the filters applied"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				if numTuples == 0: # no suspended cards
					filterError = "There are no breezecards meeting this criteria. Click reset or enter new criteria"
					# show empty table
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=[], valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				subList = []
				for breezecard in breezecards:
					breezecardRow = []
					suspended = False
					count = 0
					for data in breezecard:
						if count == 0:
							try:
								dbCursor.execute("""SELECT * FROM `Conflict` WHERE `BreezecardNum` = %s""", [data])
								# see if card is suspended
								suspendedCard = dbCursor.rowcount
								if (suspendedCard > 0):
									suspended = True
							except:
								pass
							breezecardRow.append(' '.join([data[i:i+4] for i in range(0, len(data), 4)]))
						elif count == 2:
							if data == None: # a breezecard with None in BelongsTo will never be suspended
								breezecardRow.append("---")
							else:
								if (suspended):
									breezecardRow.append("*** Suspended ***")
								else:
									breezecardRow.append(data)
						else:
							breezecardRow.append(data)
						count += 1
					subList.append(breezecardRow)
				breezecardList = subList

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

		elif "reset" in request.form:

			breezecardList = get_all_breezecards()

		elif "setValue" in request.form:

			breezecard = request.form["breezecard"]
			breezecard = breezecard.replace(" ", "") # remove extraneous spaces
			value = request.form["value"]

			breezecardCount = None 	# placeholder

			try:
				dbCursor.execute("""SELECT * FROM `Breezecard` WHERE `BreezecardNum` = %s""", [breezecard])

				breezecardCount = dbCursor.rowcount

			except:
				valueError = "Couldn't get breezecard at the moment"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# only gets here if no exception - breezecardCount has value
			if breezecardCount > 0: # breezecard exists in DB

				try:
					# give breezecard new value - doesn't matter if in trip
					dbCursor.execute("""UPDATE `Breezecard` SET `Value` = %s WHERE `BreezecardNum` = %s""", [value, breezecard])

				except:
					valueError = "Unable to update value of breezecard at the moment. Or value exceeds $1000.00"
					return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				db.commit()					# commit changes
				dbCursor.close()
				db.close()

				# update list of breezecards
				breezecardList = get_all_breezecards()

				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			else:
				valueError = "Breezecard doesn't exist. Provide a valid one from the table"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

		elif "transfer" in request.form:

			newOwner = request.form["newOwner"]
			cardNumber = request.form["cardNumber"]
			cardNumber = cardNumber.replace(" ", "") 	# remove extraneous spaces from card number

			cardCount = None 	# placeholder value
			cardTuple = None

			try:
				# see if breezecard exists in the database
				dbCursor.execute("""SELECT * FROM `Breezecard` WHERE `BreezecardNum` = %s""", [cardNumber])

				cardCount = dbCursor.rowcount 		# either 0 or 1 if doesn't exist or does
				cardTuple = dbCursor.fetchall()		# will either be empty or have just one tuple

			except:
				transferError = "Couldn't get desired breezecard at the moment"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# only gets here if no exception - cardCount has value
			ownerCount = None 	# placeholder value

			try:
				# see if user exists in database and is not an admin
				dbCursor.execute("""SELECT * FROM `User` WHERE `Username` = %s AND `IsAdmin` = 0""", [newOwner])

				ownerCount = dbCursor.rowcount	# either 0 or 1 if doesn't exist or does

			except:
				transferError = "Couldn't get desired username at the moment"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			# only gets here if no exception - cardCount and ownerCount have value
			if cardCount > 0 and ownerCount > 0: 	# both exist in the database

				usersCards = None 				# placeholder
				currentOwner = cardTuple[0][2]		# BelongsTo value

				if currentOwner == None:		# BelongsTo is NULL (and inherently not in a trip)
					try:
						# give card to this new owner
						dbCursor.execute("""UPDATE `Breezecard` SET `BelongsTo` = %s WHERE `BreezecardNum` = %s""", [newOwner, cardNumber])

						db.commit()				# commit changes
						dbCursor.close()
						db.close()

						db = openDb()				# re-open database
						dbCursor = db.cursor()

					except:
						transferError = "Couldn't transfer card to new user at the moment"
						return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

				else:		# there is an actual owner (not NULL)

					try:
						# get number of breezecards for current card owner
						dbCursor.execute("""SELECT `BelongsTo`, COUNT(*) FROM `Breezecard` WHERE `BelongsTo` = %s GROUP BY `BelongsTo`""", [currentOwner])

						# previous owner has at least one card
						usersCards = dbCursor.fetchall() # >= 1

					except:
						transferError = "Couldn't retrieve number of breezecards for previous owner"
						return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

					cardInTrip = None 	# placeholder

					try:
						# check if this card is currently in a trip
						dbCursor.execute("""SELECT * FROM `Trip` WHERE `BreezecardNum` = %s AND `EndsAt` IS NULL""", [cardNumber])

						cardInTrip = dbCursor.rowcount 	# either 0 or 1 if not in trip or is

					except:
						transferError = "Couldn't see if card is currently in a trip at the moment"
						return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

					if cardInTrip == 0: 	# card is not in trip - check count of user's breezecards

						# whether or not the user has 1 or more cards, both do the following procedure of updating card ownership and clearing conflicts
						try:
							# previous owner has more than one card and card is not in trip - assign card to new owner and reset value
							dbCursor.execute("""UPDATE `Breezecard`	SET `BelongsTo` = %s, Value = 0
												WHERE `BelongsTo` = %s AND `BreezecardNum` = %s""", [newOwner, currentOwner, cardNumber])

						except:
							transferError = "Couldn't transfer card at the moment"
							return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

						db.commit()				# commit changes
						dbCursor.close()
						db.close()

						db = openDb()				# re-open database
						dbCursor = db.cursor()

						try:
							# resolve all conflicts - if any
							dbCursor.execute("""DELETE FROM `Conflict` WHERE `BreezecardNum` = %s""", [cardNumber])

						except:
							transferError = "Couldn't assign card to new owner"
							return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

						db.commit()				# commit changes
						dbCursor.close()
						db.close()

						db = openDb()				# re-open database
						dbCursor = db.cursor()

						# cardCount won't be None if gets here - exception would've been handled
						if usersCards[0][1] == 1: # user has only this card - extra functionality to give them a new one

							# give current owner a newly generate breezecard
							generate_breezecard(dbCursor, currentOwner)

					else:	# card is in a trip
						transferError = "This card is currently in a trip. Can't reassign at the moment"
						return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			elif cardCount == 0: 	# username exists but card doesn't
				transferError = "This breezecard number doesn't exist"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			elif ownerCount == 0:	# breezecard exists but owner doesn't
				transferError = "This username doesn't exist or is an admin"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

			else:
				transferError = "Unable to transfer card to desired user"
				return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)


	db.commit()
	dbCursor.close()
	db.close()

	breezecardList = get_all_breezecards()

	return render_template("admin_breezecards.html", filterError=filterError, breezecardList=breezecardList, valueError=valueError, transferError=transferError, loadError=loadError, loadNote=loadNote, filterNote=filterNote)

@app.route('/passenger', methods=['POST', 'GET'])
def passenger():
	return render_template("passenger.html")
