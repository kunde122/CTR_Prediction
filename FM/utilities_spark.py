# coding:utf-8
import pandas as pd
import pickle
import logging
from pyspark import SparkContext
from pyspark.sql import SQLContext
from pyspark.sql.functions import udf,col
from pyspark.sql.types import *

import os
# from scipy.sparse import coo_matrix
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s',level=logging.INFO)
os.environ["PYSPARK_PYTHON"]='/home/caozhentian/miniconda3/bin/python'
def one_hot_representation(sample, fields_dict, isample):
    """
    One hot presentation for every sample data
    :param fields_dict: fields value to array index
    :param sample: sample data, type of pd.series
    :param isample: sample index
    :return: sample index
    """
    index = []
    #[样本id,样本特征值->id]
    for field in fields_dict:
        # get index of array
        if field == 'hour':
            #YYMMDDHH 最后两位表示小时
            field_value = int(str(sample[field])[-2:])
        else:
            field_value = sample[field]
        ind = fields_dict[field][field_value]
        index.append([isample,ind])
    return index

def train_sparse_data_generate(train_data, fields_dict):
    sparse_data = []
    # batch_index
    ibatch = 0
    for data in train_data:
        labels = []
        indexes = []
        for i in range(len(data)):
            sample = data.iloc[i,:]
            click = sample['click']
            # get labels
            if click == 0:
                label = 0
            else:
                label = 1
            labels.append(label)
            # get indexes
            index = one_hot_representation(sample,fields_dict, i)
            indexes.extend(index)
        sparse_data.append({'indexes':indexes, 'labels':labels})
        ibatch += 1
        if ibatch % 200 == 0:
            logging.info('{}-th batch has finished'.format(ibatch))
    with open('../avazu_CTR/train_sparse_data_frac_0.01.pkl','wb') as f:
        pickle.dump(sparse_data, f)

def test_sparse_data_generate(test_data, fields_dict):
    sparse_data = []
    # batch_index
    ibatch = 0
    for data in test_data:
        ids = []
        indexes = []
        for i in range(len(data)):
            sample = data.iloc[i,:]
            ids.append(sample['id'])
            index = one_hot_representation(sample,fields_dict, i)
            indexes.extend(index)
        sparse_data.append({'indexes':indexes, 'id':ids})
        ibatch += 1
        if ibatch % 200 == 0:
            logging.info('{}-th batch has finished'.format(ibatch))
    with open('../avazu_CTR/test_sparse_data_frac_0.01.pkl','wb') as f:
        pickle.dump(sparse_data, f)

sc = SparkContext("spark://192.168.40.21:7077","Simple")

count=sc.accumulator(0)
def map_func(sample):
    global count
    count+=1
    click = sample['click']
    # get labels
    if click == 0:
        label = 0
    else:
        label = 1
    # get indexes
    ind=count.value%10000
    index = one_hot_representation(sample, fields_dict, ind)
    return (count.value/10000,(index,label))

def proc_data():

    sqlc = SQLContext(sc)
    data_labels = sqlc.read.format('com.databricks.spark.csv').options(header='true', inferschema='true').load("hdfs://192.168.40.21:8515/user/train_1m_10w")
    data_labels.show()
    index_list = [x for x in range(1, data_labels.count() + 1)]
    idx = sc.accumulator(0)

    # 定义一个函数
    def set_index(x):
        global idx  # 将idx设置为全局变量
        idx += 1
        return index_list[idx.value - 1]

    id_udf=udf(set_index,IntegerType())
    newdata=data_labels.select(col('*'),id_udf('site_id').alias("index"))
    newdata.show()
    # data_labels.repartition(1)
    res=data_labels.rdd.map(map_func)
    fgd=res.collect()
    hr=0
# generate batch indexes
if __name__ == '__main__':
    proc_data()

    fields = ['hour', 'C1', 'C14', 'C15', 'C16', 'C17', 'C18', 'C19', 'C20', 'C21',
              'banner_pos', 'site_id' ,'site_domain', 'site_category', 'app_domain',
              'app_id', 'app_category', 'device_model', 'device_type', 'device_id',
              'device_conn_type']

    batch_size = 512
    # train = pd.read_csv('../avazu_CTR/train_frac_0.01.csv', chunksize=batch_size)
    # test = pd.read_csv('../avazu_CTR/test.csv', chunksize=batch_size)
    # loading dicts
    fields_dict = {}
    for field in fields:
        with open('/Users/user/code/mycode/CTR_Prediction/FM/'+'dicts/'+field+'.pkl','rb') as f:
            fields_dict[field] = pickle.load(f)

    # test_sparse_data_generate(test, fields_dict)
    path = 'D:\\BaiduNetdiskDownload\\train_1m'
    path = '/Users/user/Downloads/avazu-ctr-prediction/train_1m'
    train = pd.read_csv(path, chunksize=10000)
    train_sparse_data_generate(train, fields_dict)











