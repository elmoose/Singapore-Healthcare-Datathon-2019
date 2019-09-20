import pandas as pd
import os
import numpy as np
path = 'D:\Datathon\code'
os.chdir(path)

admission_date_col = 'adm__datetime_new'
discharge_date_col = 'dis_datetime_new'
adm_col = 'adm__datetime'
dis_col = 'dis_datetime'
id_col = 'patient_no_no'
visitData = pd.read_csv('../data/LACE_raw_2tables.csv', engine='python')

#convert admission and discharge time to datetime form
def adm_date(x):
    a = pd.to_datetime(x[adm_col])
    if a.year < 2010:
        print(x[adm_col])
        a = pd.NaT
    return a
visitData[admission_date_col] = visitData.apply(adm_date, axis=1)
def dis_date(x):
    try:
        a = pd.to_datetime(x[dis_col])
    except:
        print(x[dis_col])
        a = pd.NaT
    return a
visitData[discharge_date_col] = visitData.apply(dis_date, axis=1)

'''
#function: get the label 'whether readmission in next n days' for each case of visit
           find avaliable visits for prediction
           (6 months later than the first record, 1 month earlier than the last record, date is reasonable)
#input: n_front, days to cut in front, default is 180
        n_last, days to cut at last, default is 30
'''
def get_label_and_available(visitData, n_front=180, n_last=30):
    # available
    first_record = visitData[admission_date_col].min()
    last_record = pd.to_datetime('2016-12-31 23:59:59 UTC') # instead of visitData[discharge_date_col].max()
    visitData['available'] = visitData.apply(lambda x: 1 if pd.isnull(x[admission_date_col])==False and pd.isnull(x[discharge_date_col])==False and\
             (x[admission_date_col]-first_record).days>n_front and (last_record-x[discharge_date_col]).days>30 else 0, axis=1)
    # label
    ov = visitData[[id_col,admission_date_col,discharge_date_col]]
    ov_mg = pd.merge(ov.drop([admission_date_col],axis=1), ov.drop([discharge_date_col],axis=1), on=[id_col]).rename(columns={admission_date_col:'next_'+admission_date_col})
    ov_mg['time_interval'] = ov_mg.apply(lambda x: (x['next_'+admission_date_col]-x[discharge_date_col]).days, axis=1)
    ov_mg = ov_mg[ov_mg['time_interval']>0]
    ov_min = ov_mg.groupby([id_col,discharge_date_col])['time_interval'].min().reset_index()
    ov_mg = pd.merge(ov_min, ov_mg, on=[id_col,discharge_date_col,'time_interval'], how='left').groupby([id_col,discharge_date_col]).first().reset_index()
    ov_mg['LABEL_readmission'] = ov_mg.apply(lambda x: 1 if x['time_interval']<=n_last else 0, axis=1)
    visitData = pd.merge(visitData, ov_mg.drop(['time_interval'],axis=1), on=[id_col,discharge_date_col], how='left')
    return visitData

visitData = get_label_and_available(visitData)
visitData = visitData.fillna({'LABEL_readmission':0})
# drop duplicate
visitData = visitData.groupby([id_col,adm_col]).first().reset_index()
'''
# count
import matplotlib.pyplot as plt
plt.hist(visitData.apply(lambda x: x[admission_date_col].year,axis=1))
plt.hist(visitData.apply(lambda x: x[discharge_date_col].year,axis=1))
'''

# data exploration
# count the positive and negative samples
print('total visits', visitData.shape[0])
print('available visits', sum(visitData['available']))
avaData = visitData[visitData['available']==1]
print('label 1', sum(avaData['LABEL_readmission']), sum(avaData['LABEL_readmission'])/avaData.shape[0])
print('label 0', avaData.shape[0]-sum(avaData['LABEL_readmission']), 1-sum(avaData['LABEL_readmission'])/avaData.shape[0])
# save results
visitData[[id_col,adm_col,dis_col,'case_no','LABEL_readmission','available']].to_csv('../data/visits_with_label_and_avalable.csv', index=False)
# count of visits
visitCounts = avaData.groupby([id_col])[adm_col].count().reset_index()
visitCounts.groupby([adm_col])[id_col].count()

# categorys of the data
data = pd.read_csv('../data/merged_no_delete_nan.csv', engine='python')
data = data[pd.isnull(data['patient_no_no_y'])==False]
# fill missing values
data = data.fillna({'child_normal_em_ind':'normal', 'choice_class':'B2', 'country_of_origin':'Singaporean'})
# to category and one hot
from collections import Counter
writer = pd.ExcelWriter('../rslt/category_map.xlsx', engine='xlsxwriter')
cols = data.columns.values
delcols1 = ['cci_score', 're_adm_ind', 'secondary_diagnosis_codes_subvention',
            'primary_diagnosis_code_subvention','date_time','death_date',
            'adm_trt_cat_code',# duplicate columns with trt_cat_desc
            'adm_subspecialty_desc',# too much values, meaningless
            'adm_nur_ou_code', 'adm_trt_cat_desc', 'case_specialty_code', 'dis_trt_cat_code', # too much unique values
            'rehab_los_days','social_over_stayer_ind','well_baby_ind','case_type',\
            'case_visit_status'] # only 1 unique value
label_and_marks = ['patient_no_no_y','dis_datetime_y','adm__datetime','LABEL_readmission']
col_of_no = ['no_of_secondary_diagnosis_icd10','no_of_secondary_diagnosis_subvention',
             'no_of_subspecialities','no_of_surgical_operation','los_days','patient_dob']
cols = np.setdiff1d(cols, delcols1)
cols = np.setdiff1d(cols, label_and_marks)
cols = np.setdiff1d(cols, col_of_no)
newData = pd.DataFrame()
feature_column_names = col_of_no
for col in label_and_marks:
    newData[col] = data[col]
# normalization of numbers
from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
num_std = scaler.fit_transform(data[col_of_no].values)
newData[col_of_no] = pd.DataFrame(num_std)
# category and one hot
for col in cols:
    count = dict(Counter(data[col]))
    if np.nan in count.keys():
        print(col, 'nan')
    print(col, len(count.keys()))
    # number of keys
    n_key = len(count.keys())
    colMap = {}
    for i in range(n_key):
        colMap[list(count.keys())[i]] = i
    # save map for looking up
    pd.DataFrame.from_dict(colMap, orient='index',columns=['category_number']).to_excel(writer,col,index=True)
    #category number
    newData[col] = data.apply(lambda x: np.nan if pd.isnull(x[col]) else colMap[x[col]], axis=1)
    #onehot
    if n_key > 2:
        renameList = {}
        for v in colMap.values():
            renameList[float(v)] = col+'_'+str(int(v))
        # default np.nan will be all 0
        dummyData = pd.get_dummies(newData[col]).rename(columns=renameList)
        newData = pd.concat([newData, dummyData],axis=1)
        feature_column_names.extend(list(renameList.values()))
    else:
        feature_column_names.append(col)
writer.save()
# save newData
newData.dropna().to_csv('../rslt/data_after_preprocess.csv', index=False)
file = open('../rslt/feature_columns_names.txt','w')
for s in feature_column_names:
    file.write(s+'\n')
file.close()

data[col].describe()

dict(Counter(data['referral_type_from']))

# read feature_column_name.txt in python
feature_list = []
file = open('../rslt/feature_columns_names.txt')
for line in file:
    feature_list.append(line)
file.close()