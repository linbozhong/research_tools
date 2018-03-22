#### 快速入门

- 本模块可用于vnpy和jaqs的数据对接。使用之前需预先装好vnpy和jaqs。
版本号：vnpy1.8.0， jaqs0.6.1
- 连接jaqs的api需要token，要先去jaqs注册。


1. 修改config.json配置文件

- jaqs的连接信息(必须更改)：可在jaqs官网注册。注册完成后，TOKEN和ADDR信息可在官网查询。
- MONGO_HOST和MONGO_POTR默认即可。
- SYMBOLS保存要批量下载的合约列表，如果是空列表，运行批量下载前，必须运行setSymbols方法传入要批量下载的合约列表。

2. 修改contract.json(非必须)
- contract文件保存jaqs四大期货交易所的市场代码和合约的映射关系。一般不需要修改，有新上市合约才需要手动添加。

3. 批量下载合约方法
    1. 创建DataDownloader对象：
    `dl = DataDownloader()`
    2. 连接jaqs的数据api：
    `dl.loginJaqsApp()`
    3. 连接数据库：
    `dl.connectDb()`
    4. 设置要批量下载的合约列表：
    `dl.setSymbols(['m1809', 'y1805'])`
    5. 运行批量下载的方法：
   ` dl.downloadAllData()`， 默认是下载当前交易日的数据，如果下载指定的交易日数据可以用
   `dl.downloadAllData(trade_date='2018-03-08')`
   
4. 其他方法
- getData()
封装了jaqs的api.bar方法，返回一个DataFrame。用__symbolConvert将交易所代码转换成jqas的专用合约代码。可在jaqs官网查询api支持的传入参数。
- saveToDb()
下载单一合约的分钟线数据并保存入数据库。


#### 联系交流：
- linbozhong@gmail.com
- QQ:2359309630