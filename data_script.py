import pymysql
from config import config as myConfig

def openDB():
    db = pymysql.connect(
        myConfig.MYSQL_DATABASE_HOST,
        myConfig.MYSQL_DATABASE_USER,
        myConfig.MYSQL_DATABASE_PASSWORD,
        myConfig.MYSQL_DATABASE_DB)
    return(db)

def import_excel():
    excel_data = """$2.75	11/05/2017 04:21:49 PM	0524 8074 2555 1662	N11	N4
$1.50	11/03/2017 09:44:11 AM	0524 8074 2555 1662	N4	N11
$10.50	11/02/2017 01:11:11 PM	1788 6137 1948 1390	BUSDOME	BUSN11
$4.00	11/02/2017 01:11:11 PM	2792 0839 6535 9460	31955	46612
$2.00	10/31/2017 10:33:10 PM	0524 8074 2555 1662	S7	N4
$3.50	10/31/2017 10:31:10 PM	7792 6850 3597 7770	E1	N3
$1.00	10/31/2017 09:30:00 PM	1325 1383 0932 5420	FP	N3
$3.50	10/28/2017 10:30:10 PM	6411 4147 3790 0960	N11	N4
$1.50	10/28/2017 10:11:13 PM	9248 3245 4825 0130	N4	N11
$1.00	10/27/2017 09:40:11 AM	8753 0757 2174 0010	N3	N4
$9.00	10/27/2017 04:31:30 AM	7301 4425 9082 5470	N4	S7
$1.50	10/10/2017 12:00:00 AM	7534 7855 6258 8930	BUSS2	BUSDOME"""
    # excel_data = excel_data.strip()
    excel_data = excel_data.replace("\n", "\t")
    excel_data = excel_data.replace(" ", "")
    excel_data = excel_data.replace("TRUE", "1")
    excel_data = excel_data.replace("NULL", "adinozzo")
    excel_data = excel_data.replace("FALSE", "0")
    excel_data = excel_data.replace("$", "")
    data_tuple = excel_data.split('\t')
    
    
    

    
    subGroupList = []
    count = 0
    while count < len(data_tuple):
        subGroup = []
        subCount = 0
        while subCount < 5:
            if subCount == 1:
                date = ""
                date_orig = data_tuple[count]
                date = date_orig[6:10] + "-" + date_orig[:2] + "-" + date_orig[3:5] + " " + date_orig[10:18]
                subGroup.append(date)
            else:
                subGroup.append(data_tuple[count])
            subCount += 1
            count += 1
        #print(subGroup)
        subGroupList.append(subGroup)
    print(subGroupList)
    
    db = openDB()
    dbCursor = db.cursor()

    for item in subGroupList:
        dbCursor.execute("""INSERT INTO `Trip` VALUES (%s, %s, %s, %s, %s)""", [item[0],item[1], item[2], item[3], item[4]])
        db.commit()
    dbCursor.close()
    db.close()

import_excel()



