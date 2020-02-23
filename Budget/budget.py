import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import requests
import calendar
from datetime import datetime
import logging
import pickle

debug = False 

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
curDay = datetime.now().date().day
curMonth = datetime.now().date().month
curYear = datetime.now().date().year
daysInMonth = calendar.monthrange(curYear, curMonth)[1]
daysRmn = daysInMonth - curDay

monthD = curMonth - 8
if (curDay > 20) :
    monthD += 1


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

##################
# START GOOGLE API
##################
def getCreds():
    '''Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    '''
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        # logger.info('1')
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not   creds or not creds.valid:
        # logger.info('2')
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

# Creation of google global params
creds = getCreds()
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

def writeSurplus(spreadsheetID, category, val):
    range = 'Sheet1!' + str(getSurplusCoords(category))
    body = { 'values' : [[val]]}

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().update(spreadsheetId=spreadsheetID,
                                range=range,
                                valueInputOption='USER_ENTERED',
                                body=body).execute()

def writeDaSu(spreadsheetID, vals):
    ret = []
    for item in vals:
        range = 'Sheet1!' + str(item[0]) + str(4 + monthD + ((curYear-2019) * 12))

        thisVal = str(int(item[1] / daysRmn)) + ' (' + str(item[1] % daysRmn) + ')'

        body = { 'values' : [[thisVal]]}
        result = sheet.values().update(spreadsheetId=spreadsheetID,
                                    range=range,
                                    valueInputOption='USER_ENTERED',
                                    body=body).execute()
        ret = ret + [str(item[1] / daysRmn),]
    return ret

def getSurplusCoords(category):
    #Calculate column
    col='J'
    if (category == 'Savings'): col = 'K'
    if (category == 'Food'): col = 'L'
    if (category == 'Transportation'): col = 'M'
    if (category == 'Desarrollo'): col = 'N'
    if (category == 'Total'): col = 'O'

    return (col + str(4 + monthD + ((curYear-2019) * 12)))

################
# END GOOGLE API
################


################
# START YNAB API
################

# YNAB Params
class YNAB:
    def __init__(self, **args):
        for (key, value) in args.items():
            setattr(self, key, value)

### Gets all transactions that we haven't learned about
def transactionQuery(obj):
    headers = {'Authorization':'Bearer ' + obj.key}
    params = {'server_knowledge':str(obj.svrKnw)}
    ret = requests.get('https://api.youneedabudget.com/v1/budgets/' + obj.budgetID + '/transactions', headers=headers)
    json = ret.json()['data']['transactions']

    obj.mainCats = {'Savings':0, 'Student Loan':0, 'Desarrollo':0, 'Alimentación':0, 'Transportation':0, 'Rent':0,
            'Renter\'s/Home Insurance':0, 'Software Subscriptions':0,'Software Subscriptions':0, 'Fitness':0,
            'Immediate Income SubCategory':0}

    for item in json:
        date = item['date']
        day = int(date[8:10])
        month = int(date[5:7])
        year = int(date[0:4])
        if (((month == curMonth and curDay <= 20 and year == curYear) or 
                (month == (curMonth -1) and day > 20 and year == curYear)) and 
                (item['category_name'])):
            # Check for pending, and don't add if it is
            if (not item['approved']):
                obj.curPending += 1
            # Put all easily categorized transactions in place
            elif (item['category_name'] in obj.mainCats.keys()):
                obj.mainCats[item['category_name']] -= item['amount'] / 1000
            # Place all others into Desarrollo category
            else:
                logger.info(str(date) + "\t\t" + str(item['amount']) + "\t\t" + str(item['category_name']))
                obj.mainCats['Desarrollo'] += item['amount'] / 1000

### Sums up categories for purposes of grouping
def catSum(obj, cats):
    sum = 0
    for cat in obj.mainCats.keys():
        if (cat in cats):
            sum += obj.mainCats[cat]
    return sum

################
# END YNAB API
################

def refreshVals():
    # YNAB Params
    ynabApiObj = YNAB(
        monthlyMaxBudgets = { 'Food' : 620, 'Bill' : 1440, 'Savings' : 1800, 
            'Transportation' : 200 , 'Desarrollo' : 300},
        budgetID = '74290913-acc1-44fa-b3ae-b2d42bcb2dd3',
        key = '42504ed2f40e2bc88d256c5a8515ce2ae3f709d782c13fb5018149b36e629d26',
        clientID='597330006370-j1hbujnq2ov2k9hk6ln67df0l5gn34g1.apps.googleusercontent.com',
        clientSecret='5P96GpaBOb6LFXipqU5Wavbw',
        mainCats = {},
        curPending = 0,
        svrKnw = 0
        ) 


    # Google Params
    spreadsheetID = '14onvCzV-8qrLy7Itx9t32IWXjxnu-4n6ybyknXZ71Ss'

    logger.info('------ Beginning Budget Management ------')

    logger.info('Querying spending by transaction...')
    transactionQuery(ynabApiObj)

    logger.info('\nSpending for ' + str(curMonth) + '/' + str(curYear) + ':')
    for item in ynabApiObj.mainCats.keys():
        logger.info(item + ': ' +  str(ynabApiObj.mainCats[item])) 
    logger.info('\n')

    logger.info('Calculating surpluses...')
    billSurplus    = ynabApiObj.monthlyMaxBudgets['Bill'] - int(catSum(ynabApiObj, ['Rent', 'Renter\'s/Home Insurance', 'Software Subscriptions', 'Fitness']))
    logger.info('Surplus for bill category: ' + str(billSurplus))
    savingsSurplus = ynabApiObj.monthlyMaxBudgets['Savings'] - int(catSum(ynabApiObj, ['Savings', 'Student Loan']))
    logger.info('Surplus for savings category: ' + str(savingsSurplus))
    foodSurplus    = ynabApiObj.monthlyMaxBudgets['Food'] - int(ynabApiObj.mainCats['Alimentación'])
    logger.info('Surplus for food category: ' + str(foodSurplus))
    transSurplus   = ynabApiObj.monthlyMaxBudgets['Transportation'] - int(ynabApiObj.mainCats['Transportation'])
    logger.info('Surplus for trans category: ' + str(transSurplus))
    funSurplus     = ynabApiObj.monthlyMaxBudgets['Desarrollo'] - int(ynabApiObj.mainCats['Desarrollo'])
    logger.info('Surplus for fun category: ' + str(funSurplus))

    logger.info('\nWriting to sheet...')
    writeSurplus(spreadsheetID, 'Bill', billSurplus)
    writeSurplus(spreadsheetID, 'Savings', savingsSurplus)
    writeSurplus(spreadsheetID, 'Food', foodSurplus)
    writeSurplus(spreadsheetID, 'Transportation', transSurplus)
    writeSurplus(spreadsheetID, 'Desarrollo', funSurplus)
    daSuParam = [('P', billSurplus),('Q', savingsSurplus),('R', foodSurplus),
            ('S', transSurplus), ('T', funSurplus)]

    dStore = writeDaSu(spreadsheetID, daSuParam)
    mStore = [billSurplus, savingsSurplus, foodSurplus, transSurplus, funSurplus]

    if (ynabApiObj.curPending > 0):
        logger.info('\n\n**********************************************************')
        logger.info('WARNING: You have ' + str(ynabApiObj.curPending) + ' pending transactions.')
        logger.info('**********************************************************\n')

    logger.info('\nProcess completed successfuly. Exiting.')
    return (mStore, dStore)

