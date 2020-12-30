from beanlabs.importers.ibkr.ibkr_flex_reports_csv import Importer
import beangrind


importer = Importer(filing="Assets:US:IBKR:Main", config={
    'root'        : "Assets:US:IBKR:Main",
    'asset_cash'  : "Assets:US:IBKR:Main:Cash",
    'fees'        : "Expenses:Financial:Fees",
    'commissions' : "Expenses:Financial:Commissions",
    'transfer'    : "Assets:US:Bank:Checking",
    'interest'    : 'Income:US:IBKR:Interest',
})
TestImporter = beangrind.regress_importer_with_files(importer, __file__)
