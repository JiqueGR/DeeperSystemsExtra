import telebot
from pymongo import MongoClient
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

token = "7326821694:AAHsi6XohwO-qpcJxfDgzZ8M0CYl6iXzmDY"
bot = telebot.TeleBot(token)

url = "mongodb+srv://JiqueGR:6nyk9fSLuOSeo8BL@deepsystem.itxh5.mongodb.net/DeepSystem?retryWrites=true&w=majority&appName=DeepSystem"
client = MongoClient(url)
db = client['DeepSystem']
bank = db['Bank']
method = db['Method']

user_data = {}

def insertBalanceRecord(model):
    bank.insert_one(model)


def insertMethodRecord(model):
    method.insert_one(model)


def getLastRecord(userId):
    return bank.find_one({"userId": userId}, sort=[('_id', -1)])


def getBalance(userId):
    lastRecord = getLastRecord(userId)
    if lastRecord:
        return lastRecord.get("balance", 0)
    return 0


def getMethods(userId):
    methods = method.find({"userId": userId})
    return list(methods)


@bot.message_handler(commands=['start'])
def startMessage(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Check Balance", callback_data="checkBalance"),
        InlineKeyboardButton("Deposit", callback_data="deposit"),
        InlineKeyboardButton("Withdraw", callback_data="withdraw")
    )
    bot.send_message(message.chat.id, "Choose an option:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["checkBalance", "deposit", "withdraw"])
def callback_query(call):
    userId = call.from_user.id

    if call.data == "checkBalance":
        lastRecord = getLastRecord(userId)

        if lastRecord:
            balance = lastRecord.get('balance', 0)
            lastTransferValue = lastRecord.get('lastTransferValue', 0)
            lastTransferType = lastRecord.get('lastTransferType', 'None')
            lastTransferTime = lastRecord.get('lastTransferTime', 'None')
            method = lastRecord.get('method', 'None')
            bot.send_message(call.message.chat.id,
                             f"Your balance is: ${balance} "
                             f"\nLast transfer value: ${lastTransferValue} "
                             f"\nLast transfer type: {lastTransferType} "
                             f"\nLast transfer time: {lastTransferTime}"
                             f"\nMethod: {method}")

        else:
            bot.send_message(call.message.chat.id, "No transaction records found.")

        fakeCall = type('FakeCall', (object,), {
            'from_user': type('User', (object,), {'id': userId}),
            'data': "startMessage",
            'message': call.message
        })
        startMessage(fakeCall.message)

    elif call.data == "deposit":
        msg = bot.send_message(call.message.chat.id, "How much do you want to deposit?")
        bot.register_next_step_handler(msg, lambda m: processDepositStep(m, userId))

    elif call.data == "withdraw":
        msg = bot.send_message(call.message.chat.id, "How much do you want to withdraw?")
        bot.register_next_step_handler(msg, lambda m: processWithdrawStep(m, userId))


def processDepositStep(message, userId):
    try:
        value = int(message.text)
        if value > 0:
            user_data[userId] = {"temporaryValue": value}
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Choose Deposit Method", callback_data="chooseDepositMethod"),
                       InlineKeyboardButton("Cancel", callback_data="cancelDeposit"))
            bot.send_message(message.chat.id, f"Do you want to deposit ${value}?", reply_markup=markup)
        else:
            raise ValueError
    except ValueError:
        msg = bot.send_message(message.chat.id, "Insert a number higher than 0")
        bot.register_next_step_handler(msg, lambda m: processDepositStep(m, userId))


@bot.callback_query_handler(func=lambda call: call.data == "chooseDepositMethod")
def chooseDepositMethod(call):
    userId = call.from_user.id
    methods = getMethods(userId)

    markup = InlineKeyboardMarkup()
    if methods:
        for method in methods:
            markup.add(
                InlineKeyboardButton(method["method"], callback_data=f"confirmDepositMethod_{method['method']}"))

    markup.add(InlineKeyboardButton("Add New Method", callback_data="addNewDepositMethod"),
               InlineKeyboardButton("Cancel", callback_data="cancelDeposit"))
    bot.send_message(call.message.chat.id, "Choose a deposit method:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirmDepositMethod_"))
def confirmDepositMethod(call):
    userId = call.from_user.id
    method = call.data.split("_")[1]

    temporaryValue = user_data.get(userId, {}).get("temporaryValue", 0)

    lastTransferTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lastTransferType = "Deposit"
    newBalance = getBalance(userId) + temporaryValue

    model = {
        "userId": userId,
        "balance": newBalance,
        "lastTransferValue": temporaryValue,
        "lastTransferTime": lastTransferTime,
        "lastTransferType": lastTransferType,
        "method": method
    }
    insertBalanceRecord(model)

    bot.send_message(call.message.chat.id,
                     f"Deposit of ${temporaryValue} with {method} succeeded! Your new balance is ${newBalance}.")
    startMessage(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "addNewDepositMethod")
def addNewDepositMethod(call):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Bank Transfer", callback_data="addBankTransfer"),
        InlineKeyboardButton("Paypal", callback_data="addPaypal"),
        InlineKeyboardButton("Crypto", callback_data="addCrypto")
    )
    bot.send_message(call.message.chat.id, "Choose a method:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["addBankTransfer", "addPaypal", "addCrypto"])
def callback_query(call):
    userId = call.from_user.id

    if call.data == "addBankTransfer":
        msg = bot.send_message(call.message.chat.id, "What is the name of your bank?")
        bot.register_next_step_handler(msg, lambda m: finalizeNewMethod(m, call.from_user.id, "Bank Transfer"))

    elif call.data == "addPaypal":
        msg = bot.send_message(call.message.chat.id, "What is your Paypal email?")
        bot.register_next_step_handler(msg, lambda m: finalizeNewMethod(m, call.from_user.id, "Paypal"))

    elif call.data == "addCrypto":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("BTC", callback_data="addCryptoBTC"),
            InlineKeyboardButton("ETH", callback_data="addCryptoETH"),
            InlineKeyboardButton("USDT", callback_data="addCryptoUSDT")
        )
        bot.send_message(call.message.chat.id, "Choose a cryptocurrency:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("addCrypto"))
def processCryptoChoice(call):
    crypto_type = call.data[-3:]
    msg = bot.send_message(call.message.chat.id, f"What is your {crypto_type} wallet address?")
    bot.register_next_step_handler(msg, lambda m: finalizeNewMethod(m, call.from_user.id, f"Crypto ({crypto_type})"))


def finalizeNewMethod(message, userId, method):
    model = {
        "userId": userId,
        "method": str(method) + ": " + message.text
    }
    insertMethodRecord(model)

    bot.send_message(message.chat.id, f"New deposit method added: {method}: {message.text}.")
    fakeCall = type('FakeCall', (object,), {
        'from_user': type('User', (object,), {'id': userId}),
        'data': "chooseDepositMethod",
        'message': message
    })
    chooseDepositMethod(fakeCall)


@bot.callback_query_handler(func=lambda call: call.data == "cancelDeposit")
def cancelDeposit(call):
    bot.send_message(call.message.chat.id, "Deposit canceled.")
    startMessage(call.message)


def processWithdrawStep(message, userId):
    try:
        value = int(message.text)
        current_balance = getBalance(userId)

        if 0 < value <= current_balance:
            user_data[userId] = {"temporaryValue": value}
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Choose Withdraw Method", callback_data="chooseWithdrawMethod"),
                       InlineKeyboardButton("Cancel", callback_data="cancelWithdraw"))
            bot.send_message(message.chat.id, f"Do you want to withdraw ${value}?", reply_markup=markup)
        else:
            raise ValueError
    except ValueError:
        msg = bot.send_message(message.chat.id, "Insert a valid number within your balance.")
        bot.register_next_step_handler(msg, lambda m: processWithdrawStep(m, userId))

@bot.callback_query_handler(func=lambda call: call.data == "chooseWithdrawMethod")
def chooseWithdrawMethod(call):
    userId = call.from_user.id
    methods = getMethods(userId)

    markup = InlineKeyboardMarkup()
    if methods:
        for method in methods:
            markup.add(InlineKeyboardButton(method["method"], callback_data=f"confirmWithdrawMethod_{method['method']}"))

    markup.add(InlineKeyboardButton("Add New Method", callback_data="addNewWithdrawMethod"),
               InlineKeyboardButton("Cancel", callback_data="cancelWithdraw"))
    bot.send_message(call.message.chat.id, "Choose a withdraw method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirmWithdrawMethod_"))
def confirmWithdrawMethod(call):
    userId = call.from_user.id
    method = call.data.split("_")[1]

    temporaryValue = user_data.get(userId, {}).get("temporaryValue", 0)
    lastTransferTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lastTransferType = "Withdraw"
    newBalance = getBalance(userId) - temporaryValue

    model = {
        "userId": userId,
        "balance": newBalance,
        "lastTransferValue": temporaryValue,
        "lastTransferTime": lastTransferTime,
        "lastTransferType": lastTransferType,
        "method": method
    }
    insertBalanceRecord(model)

    bot.send_message(call.message.chat.id,
                     f"Withdrawal of ${temporaryValue} with {method} succeeded! Your new balance is ${newBalance}.")
    startMessage(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "addNewWithdrawMethod")
def addNewWithdrawMethod(call):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Bank Transfer", callback_data="addWithdrawBankTransfer"),
        InlineKeyboardButton("Paypal", callback_data="addWithdrawPaypal"),
        InlineKeyboardButton("Crypto", callback_data="addWithdrawCrypto")
    )
    bot.send_message(call.message.chat.id, "Choose a withdraw method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("addWithdraw"))
def processAddWithdrawMethod(call):
    method_type = call.data.replace("addWithdraw", "")
    msg = bot.send_message(call.message.chat.id, f"Provide details for {method_type}.")
    bot.register_next_step_handler(msg, lambda m: finalizeNewMethod(m, call.from_user.id, method_type, "withdraw"))

@bot.callback_query_handler(func=lambda call: call.data == "cancelWithdraw")
def cancelWithdraw(call):
    bot.send_message(call.message.chat.id, "Withdrawal canceled.")
    startMessage(call.message)


bot.polling()
