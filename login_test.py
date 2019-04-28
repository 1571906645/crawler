import requests
from requests.exceptions import ConnectionError
import re
from bs4 import BeautifulSoup
import os
from zipfile import ZipFile
from PIL import Image
from threading import Thread
import json
import tkinter as tk
from tkinter import ttk
import socket
import time

_dnscache = dict()


def _setdnscache():
    # DNS缓存

    def _getaddrinfo(*args, **kwargs):
        if args in _dnscache:
            # print('使用了dns缓存:%s' % _dnscache[args])
            return _dnscache[args]
        else:
            _dnscache[args] = socket._getaddrinfo(*args, **kwargs)
            # print('添加dns缓存:%s' % _dnscache[args])
            return _dnscache[args]

    if not hasattr(socket, '_getaddrinfo'):
        socket._getaddrinfo = socket.getaddrinfo
        socket.getaddrinfo = _getaddrinfo


class User(object):
    # 浏览器请求头
    header = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'}
    # 登录网址
    posturl = 'https://accounts.pixiv.net/api/login?lang=zh'
    # 主页
    baseurl = 'https://www.pixiv.net'
    # 创建session
    psession = requests.session()
    downloadsession = requests.session()
    downloadsession.keep_alive = False
    # 创建一个保存作者id的集合
    id_set = set()
    userid = ''

    def __init__(self):
        return

    # self.username = username
    # self.password = password
    # self.userid = self.login()
    # self.filepath = 'Author/%s/' % self.userid

    # 模拟登录
    def login(self, username, password):
        try:
            loginkey = self.psession.get('https://accounts.pixiv.net/login', headers=self.header)
            post_key = re.search('name="post_key".*?value="(.*?)"', loginkey.text).group(1)
            postdata = {
                'password': password,
                'pixiv_id': username,
                'post_key': post_key,
            }
            login_response = self.psession.post(self.posturl, headers=self.header, data=postdata)
            userid = re.search('PHPSESSID=(.*?)_', str(self.psession.cookies))
            if not userid:
                return False
            self.userid = userid.group(1)
            # print(self.userid)
            return True
        except ConnectionError:
            return self.login(username, password)

        # 获取关注的所有画师id并存入id_set

    def member(self, url='https://www.pixiv.net/bookmark.php?type=user'):
        pixivresponse = self.psession.get(url, headers=self.header)
        soup = BeautifulSoup(pixivresponse.text, 'lxml')
        cla = soup.find(class_='members')
        pages = soup.find(class_='_pager-complex')
        members = cla.find_all('li')
        for i in members:
            id = re.search('href=".*?=(.*?)"', str(i)).group(1)
            self.id_set.add(id)
            # print(id)
        if pages:
            print(str(pages))
            nextpage = re.search('<a class="button" href="(.*?)" rel="next">', str(pages))
            if nextpage:
                print(nextpage.group(1))
                self.member(url='https://www.pixiv.net/bookmark.php' + nextpage.group(1).replace('&amp;', '&'))
        return

    # 根据画师id获取该画师的所有作品id
    def member_id(self, id='4754550'):
        ajax_url = 'https://www.pixiv.net/ajax/user/' + id + '/profile/all'
        id_url = 'https://www.pixiv.net/member_illust.php?id=' + id
        json_file = self.psession.get(ajax_url, headers=self.header)
        # print(memberresponse.text)
        id_dir = json_file.json()['body']['illusts']
        for id in id_dir.keys():
            self.save_id(id=id, filepath=2)

    # 保存收藏id
    def collection(self, id=False):
        filepath = 'Author/收藏/%s/' % self.userid
        bookmarks_url = 'https://www.pixiv.net/ajax/user/%s/illusts/bookmarks?tag=&offset=0&limit=9999&rest=show' % self.userid
        if id:
            filepath = 'Author/收藏/%s/' % id
            bookmarks_url = 'https://www.pixiv.net/ajax/user/%s/illusts/bookmarks?tag=&offset=0&limit=9999&rest=show' % id
        colresponse = self.psession.get(bookmarks_url, headers=self.header).json()
        # print(colresponse)
        for i in colresponse['body']['works']:
            self.save_id(id=i['id'], filepath=filepath)

    # 每日推荐
    def discovery(self, num):
        try:
            headers = {
                'Referer': 'https://www.pixiv.net/discovery',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
            }
            filepath = 'Author/推荐/'
            discovery_url = 'https://www.pixiv.net/rpc/recommender.php?type=illust&sample_illusts=auto&num_recommendations=1000&page=discovery&mode=all'
            disresponse = self.psession.get(discovery_url, headers=headers).json()
            # print(disresponse)
            # print(len(disresponse['recommendations']))
            for i in range(0, num):
                id = disresponse['recommendations'][i]
                self.save_id(id=id, filepath=filepath)
        except ConnectionError:
            return self.discovery(num=num)

    # 下载排行
    def rank(self, mode='daily', date=None, num=0):
        jsonurl = 'https://www.pixiv.net/ranking.php?mode=%s&date=%s&format=json' % (mode, date)
        filepath = 'Author/排行/%s/%s/' % (mode, date)
        jsonres = self.psession.get(jsonurl, headers=self.header)
        if jsonres.status_code == 200:
            rankdate = jsonres.json()
            # print(len(rankdate['contents']))
            for i in range(0, num):
                id = rankdate['contents'][i]['illust_id']
                self.save_id(id=id, filepath=filepath)

    # 根据作品id得到图片url和Referer
    def save_id(self, id=None, filepath=None):
        try:
            _setdnscache()
            id_url = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(id)
            more_url = 'https://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(id)
            id_ajax = 'https://www.pixiv.net/ajax/illust/' + str(id)
            idresponse = self.psession.get(id_ajax, headers=self.header)
            img = idresponse.json()['body']['urls']['original']
            imgnum = idresponse.json()['body']['pageCount']
            imgtype = idresponse.json()['body']['illustType']
            if filepath == None:
                filepath = 'Author/ids/'
            elif filepath == 2:
                title = idresponse.json()['body']['userName']
                filepath = 'Author/members/%s/' % title
            if not os.path.exists(filepath):
                os.makedirs(filepath)
            if imgnum > 1:
                for i in range(0, imgnum):
                    newimg = img.replace('_p0', '_p' + str(i))
                    self.save_file(url=id_url, img=newimg, filepath=filepath)
            else:
                self.save_file(url=id_url, img=img, filepath=filepath)
            if imgtype == 2:
                self.save_gif(id=id, idpath=filepath)
        except ConnectionError:
            return self.save_id(id=id, filepath=filepath)

    # 保存图片
    def save_file(self, url, img, filepath):
        _setdnscache()
        save_headers = {
            'Referer': url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
        }
        name = img.split('/')[-1]
        if os.path.isfile(filepath + name):
            return print(name + '已存在')
        res = self.downloadsession.get(img, headers=save_headers)
        if res.status_code == 200:
            with open(filepath + name, 'wb') as f:
                f.write(res.content)
                f.close()
        return print(name)

    # 保存动图
    def save_gif(self, id, idpath):
        _setdnscache()
        if os.path.isfile(idpath + str(id) + '.gif'):
            return print(id + '.gif已存在')
        href = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(id)
        headers = {
            'Referer': href,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
        }
        res = requests.get(href, headers=headers)
        urls = re.findall('"(https://i\.pximg\..*?' + str(id) + '.*?)"', res.text)
        url = urls[-1]
        zurl = url.replace('c/128x128/img-master', 'img-zip-ugoira').replace('square1200.jpg', 'ugoira1920x1080.zip')
        # zzurl = zurl.replace('1920x1080', '600x600')
        dirpath = 'Iimgs/' + str(id) + '/'
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        response = requests.get(zurl, headers=headers)
        if response.status_code == 200:
            # print(zurl)
            name = zurl.split('/')[-1]
            with open('Iimgs/' + name, 'wb') as f:
                f.write(response.content)
                f.close()
            zf = ZipFile('Iimgs/' + name, 'r')
            for file in zf.namelist():
                zf.extract(file, dirpath)
            zf.close()
            # self.imgname(dirpath)
            frames = []
            imglist = os.listdir(dirpath)
            for img in imglist:
                if os.path.exists(dirpath + img):
                    frames.append(Image.open(dirpath + img))
            frames[0].save(idpath + str(id) + '.gif', save_all=True, append_images=frames[1:], duration=1 / 24,
                           format='GIF', loop=0)
            # os.system('ffmpeg -r 24 -i ' + dirpath + '%d.jpg ' + idpath + str(id) + '.gif')
            self.del_file(dirpath)
            os.remove('Iimgs/' + name)
            response.close()
            return

    # 清理解压内容
    def del_file(self, path):
        ls = os.listdir(path)
        for i in ls:
            d_path = os.path.join(path, i)
            if os.path.isdir(d_path):
                self.del_file(d_path)
            else:
                os.remove(d_path)
        os.rmdir(path)
        return

    # 重命名解压文件
    # def imgname(self, path):
    #     dirs = os.listdir(path)
    #     for img in dirs:
    #         img_path = os.path.join(path, img)
    #         while img.startswith('0') and len(img) >= 6:
    #             img = img[1:]
    #         newpath = os.path.join(path, img)
    #         os.rename(img_path, newpath)

    # 下载关注的画师
    def author(self):
        self.member()
        if '11' in self.id_set:
            self.id_set.remove('11')
        # print(self.id_set)
        threads = []
        for m_id in self.id_set:
            t = Thread(target=self.member_id, args=(m_id,))
            threads.append(t)
        threadnum = len(threads)
        for i in range(threadnum):
            threads[i].start()
        for i in range(threadnum):
            threads[i].join()

    def pagenum(self, url, p=1, filepath=None):
        try:
            pageurl = url + str(p)
            wre = self.psession.get(pageurl, headers=self.header)
            soup = BeautifulSoup(wre.text, 'lxml')
            # print(wre.text)
            data_items = re.search('data-items="(.*?)"', wre.text).group(1)
            s = '{"body":' + data_items.replace('&quot;', '"') + '}'
            # print(s)
            # print(data_items.encode('latin-1').decode('unicode_escape'))
            jsondata = json.loads(s, encoding='utf-8')
            for i in jsondata['body']:
                self.save_id(i["illustId"], filepath=filepath)
            lis = soup.find(class_='page-list')
            if not lis:
                return 1
            li = lis.find_all('li')[-1].string
            print(li)
            return int(li)
        except ConnectionError:
            return self.pagenum(url=url, p=p)

    # 根据关键字下载
    def word(self, name, num):
        filepath = 'Author/关键字/%s/' % name
        wordurl = "https://www.pixiv.net/search.php?word=%s %s&p=" % (name, num)
        # print(wordurl)
        p = 0
        while True:
            p = p + 1
            page = self.pagenum(url=wordurl, p=p, filepath=filepath)
            if p >= page:
                break


# 登录状态装饰器
def islogin(func):
    def myfunc(self, *args, **kwargs):
        if self.login_status:
            return func(self, *args, **kwargs)
        else:
            return self.evar.set('请先登录')

    return myfunc


class MyThread(Thread):
    def __init__(self, func, args=()):
        super(MyThread, self).__init__()
        self.func = func
        self.args = args

    def run(self):
        self.result = self.func(*self.args)

    def get_result(self):
        try:
            return self.result
        except Exception:
            return None


class App(object):
    a = User()
    login_status = False

    def __init__(self, master):
        frame = tk.Canvas(master)
        frame.pack()
        # 登录框
        ttk.Label(master, text='用户名', font=('Arial', 12)).place(x=50, y=50)
        self.eu = ttk.Entry(master, show=None)
        self.eu.place(x=150, y=50)
        ttk.Label(master, text='密码', font=('Arial', 12)).place(x=50, y=100)
        self.ep = ttk.Entry(master, show='.')
        self.ep.place(x=150, y=100)
        self.evar = tk.StringVar()
        error = ttk.Label(master, textvariable=self.evar, font=('Arial', 12))
        error.place(x=200, y=150)
        ttk.Button(master, text='登录', command=self.user_pass).place(x=100, y=150)
        # 个人下载框
        ttk.Button(master, text='下载收藏的图片', command=self.mycollection).place(x=400, y=50)
        ttk.Button(master, text='下载关注的画师图片', command=self.mymember).place(x=400, y=100)
        self.disnum = ttk.Entry(master, show=None)
        self.disnum.place(x=400, y=150, width=50)
        ttk.Button(master, text='下载推荐的图片1-999张', command=self.discovery).place(x=400, y=180)
        # 图片id下载框
        ttk.Label(master, text='输入图片id', font=('Arial', 12)).place(x=0, y=200)
        self.pid = ttk.Entry(master, show=None)
        self.pid.place(x=100, y=200, width=100)
        ttk.Button(master, text='下载', command=self.getid).place(x=220, y=200)
        ttk.Label(master, text='无需登录', font=('Arial', 12)).place(x=320, y=200)
        # 用户id下载框
        ttk.Label(master, text='输入用户id', font=('Arial', 12)).place(x=0, y=250)
        self.uid = ttk.Entry(master, show=None)
        self.uid.place(x=100, y=250, width=100)
        ttk.Button(master, text='下载用户作品', command=self.getuserwork).place(x=220, y=250)
        ttk.Button(master, text='下载用户收藏', command=self.getusercol).place(x=320, y=250)
        # 关键字下载框
        ttk.Label(master, text='输入关键字', font=('Arial', 12)).place(x=0, y=300)
        self.kword = ttk.Entry(master, show=None)
        self.kword.place(x=100, y=300, width=100)
        ttk.Button(master, text='下载收藏大于5000', command=self.getkey_5000).place(x=220, y=300)
        ttk.Button(master, text='下载收藏大于10000', command=self.getkey_10000).place(x=350, y=300)
        # 排行框
        ttk.Label(master, text='年', font=('Arial', 12)).place(x=10, y=330)
        ttk.Label(master, text='月', font=('Arial', 12)).place(x=70, y=330)
        ttk.Label(master, text='日', font=('Arial', 12)).place(x=130, y=330)
        ttk.Label(master, text='下载多少张(1-50)?', font=('Arial', 12)).place(x=200, y=330)
        self.ranknum = ttk.Entry(master, show=None)
        self.ranknum.place(x=200, y=360, width=50)
        nowyear = int(time.strftime('%Y'))
        self.year = ttk.Combobox(master, values=[i for i in range(2010, nowyear + 1)], state='readonly')
        self.year.set(nowyear)
        self.year.bind("<<ComboboxSelected>>", self.daynum)
        self.year.place(x=10, y=360, width=50)
        self.month = ttk.Combobox(master, values=[i for i in range(1, 13)], state='readonly')
        self.month.bind("<<ComboboxSelected>>", self.daynum)
        self.month.place(x=70, y=360, width=50)
        self.dayvar = tk.IntVar()
        self.day = ttk.Combobox(master, state='readonly')
        ttk.Button(master, text='按月', command=lambda: self.get_rank(mode='monthly')).place(x=260, y=360, width=40)
        ttk.Button(master, text='按周', command=lambda: self.get_rank(mode='weekly')).place(x=305, y=360, width=40)
        ttk.Button(master, text='按日', command=lambda: self.get_rank(mode='daily')).place(x=350, y=360, width=40)
        ttk.Label(master, text='建议下载完成后使用', font=('Arial', 10)).place(x=420, y=340)
        ttk.Button(master, text='去除排行中重复的图', command=self.delfile).place(x=420, y=360, width=120)

    # 设置动态的day下拉框
    def daynum(self, *args):
        yy = self.year.get()
        mm = self.month.get()
        # print(yy)
        # print(mm)
        if yy and mm:
            self.dayvar.set(get_day(int(yy), int(mm)))
            self.day['values'] = [i for i in range(1, self.dayvar.get() + 1)]
            self.day.current(0)
            self.day.place(x=130, y=360, width=50)
        return None

    def user_pass(self):
        user = self.eu.get()
        password = self.ep.get()
        if user and password:
            t = MyThread(self.a.login, args=(user, password))
            t.start()
            t.join()
            message = t.get_result()
            if message:
                self.login_status = True
                self.evar.set('用户%s登录成功' % self.a.userid)
            else:
                self.evar.set('账号或密码错误')
            return
        else:
            self.evar.set('输入用户名和密码')
            return False

    @islogin
    def mycollection(self):
        t = Thread(target=self.a.collection)
        t.start()
        return self.evar.set('下载中')

    @islogin
    def mymember(self):
        t = Thread(target=self.a.author)
        t.start()
        return self.evar.set('下载中')

    def getid(self):
        id = self.pid.get()
        rid = re.match('^[1-9][0-9]{5,7}$', id)
        if not rid:
            return self.evar.set('请输入正确的id')
        t = Thread(target=self.a.save_id, args=(id,))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getuserwork(self):
        id = self.uid.get()
        usid = re.match('^[1-9][0-9]{2,8}$', id)
        if not usid:
            return self.evar.set('请输入正确的id')
        t = Thread(target=self.a.member_id, args=(id,))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getusercol(self):
        id = self.uid.get()
        usid = re.match('^[1-9][0-9]{2,8}$', id)
        if not usid:
            return self.evar.set('请输入正确的id')
        t = Thread(target=self.a.collection, args=(id,))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getkey_5000(self):
        kword = self.kword.get()
        if not kword:
            return self.evar.set('关键字不能为空')
        t = Thread(target=self.a.word, args=(kword, 5000))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getkey_10000(self):
        kword = self.kword.get()
        if not kword:
            return self.evar.set('关键字不能为空')
        t = Thread(target=self.a.word, args=(kword, 10000))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def discovery(self):
        num = self.disnum.get()
        renum = re.match('^[1-9][0-9]{0,2}$', num)
        if not renum:
            return self.evar.set('输入不规范')
        num = int(num)
        t = Thread(target=self.a.discovery, args=(num,))
        t.start()
        return self.evar.set('下载中')

    def get_rank(self, mode):
        year = self.year.get()
        month = self.month.get()
        day = self.day.get()
        if year and month and day:
            if len(month) < 2:
                month = '0' + month
            if len(day) < 2:
                day = '0' + day
            rankdate = year + month + day
            print(rankdate)
            nowtime = time.strftime("%Y%m%d")
            print(nowtime)
            if rankdate >= nowtime:
                return self.evar.set('这个时间没有排行')
            num = self.ranknum.get()
            if not num:
                return self.evar.set('数字不能为空')
            numrule = re.match('(^[1-4][0-9]$)|(^50$)|(^[1-9]$)', num)
            if not numrule:
                return self.evar.set('输入1-50')
            t = Thread(target=self.a.rank, args=(mode, rankdate, int(num)))
            t.start()
            return self.evar.set('下载中')
        else:
            return self.evar.set('请选择日期')

    def delfile(self):
        t = Thread(target=del_repeat, args=(1,))
        t.start()
        return self.evar.set('删了')


def del_repeat(presence, path='Author/排行/'):
    s = set()
    ls = os.listdir(path)
    for i in ls:
        path2 = os.path.join(path, i)
        if os.path.isdir(path2):
            imgs = os.listdir(path2)
            for img in imgs:
                path3 = os.path.join(path2, img)
                if img in s:
                    os.remove(path3)
                else:
                    s.add(img)


# def save(dirpath):
#     frames = []
#     imglist = os.listdir(dirpath)
#     for i in range(len(imglist)):
#         if os.path.exists(dirpath + imglist[i]):
#             frames.append(Image.open(dirpath + imglist[i]))
#     frames[0].save('imgs/1.gif', save_all=True, append_images=frames[1:], duration=1 / 24, format='GIF',
#                    loop=0)


def get_day(y, m):
    if m in [1, 3, 5, 7, 8, 10, 12]:
        return 31
    elif m in [4, 6, 9, 11]:
        return 30
    else:
        if y % 4 == 0:
            return 29
        else:
            return 28


def main():
    root = tk.Tk()
    root.title('下载')
    root.geometry('550x400')
    app = App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
    # u = User()
