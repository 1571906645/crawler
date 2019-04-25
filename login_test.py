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


# import imageio


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
    filepath = ''

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
            userresponse = self.psession.get(self.baseurl, headers=self.header)
            userid = re.search('\[\{.*?user_id: "(\d+)".*?\}\]', userresponse.text)
            if not userid:
                return False
            self.userid = userid.group(1)
            self.filepath = 'Author/%s/' % self.userid
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
            self.save_id(id=id, favorites=True)

    # 保存收藏id
    def collection(self, id=False):
        self.filepath = 'Author/%s/' % self.userid
        bookmarks_url = 'https://www.pixiv.net/ajax/user/%s/illusts/bookmarks?tag=&offset=0&limit=9999&rest=show' % self.userid
        if id:
            self.filepath = 'Author/%s/' % id
            bookmarks_url = 'https://www.pixiv.net/ajax/user/%s/illusts/bookmarks?tag=&offset=0&limit=9999&rest=show' % id
        colresponse = self.psession.get(bookmarks_url, headers=self.header).json()
        # idlist = [i['id'] for i in colresponse['body']['works']]
        # print(colresponse)
        for i in colresponse['body']['works']:
            self.save_id(id=i['id'])

    # 根据作品id得到图片url和Referer
    def save_id(self, id=73598112, favorites=None):
        try:
            id_url = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(id)
            more_url = 'https://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(id)
            id_ajax = 'https://www.pixiv.net/ajax/illust/' + str(id)
            idresponse = self.psession.get(id_ajax, headers=self.header)
            img = idresponse.json()['body']['urls']['original']
            imgnum = idresponse.json()['body']['pageCount']
            imgtype = idresponse.json()['body']['illustType']
            filepath = self.filepath
            if favorites:
                title = idresponse.json()['body']['userName']
                filepath = 'Author/' + title + '/'
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
            return self.save_id(id=id, favorites=favorites)

    # 保存图片
    def save_file(self, url, img, filepath):
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

    def pagenum(self, url, p=1):
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
                self.save_id(i["illustId"])
            lis = soup.find(class_='page-list')
            if not lis:
                return 1
            li = lis.find_all('li')[-1].string
            print(li)
            return int(li)
        except ConnectionError:
            return self.pagenum(url=url, p=p)

    # 根据关键字下载
    def word(self, name):
        self.filepath = 'Author/%s/' % name
        wordurl_1 = "https://www.pixiv.net/search.php?word=" + name + " 5000&p="
        wordurl_2 = "https://www.pixiv.net/search.php?word=" + name + " 1000&p="
        p = 0
        while True:
            p = p + 1
            page = self.pagenum(url=wordurl_1, p=p)
            if p >= page:
                break
        p = 0
        while True:
            p = p + 1
            page = self.pagenum(url=wordurl_2, p=p)
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
        tk.Label(master, text='用户名', font=('Arial', 12)).place(x=50, y=50)
        self.eu = tk.Entry(master, show=None)
        self.eu.place(x=150, y=50)
        tk.Label(master, text='密码', font=('Arial', 12)).place(x=50, y=100)
        self.ep = tk.Entry(master, show='.')
        self.ep.place(x=150, y=100)
        self.evar = tk.StringVar()
        error = tk.Label(master, textvariable=self.evar, fg='red', font=('Arial', 12))
        error.place(x=200, y=150)
        tk.Button(master, text='登录', fg='black', width=10, height=2, command=self.user_pass).place(x=100, y=150)
        # 关注下载框
        tk.Button(master, text='下载收藏的图片', fg='black', command=self.mycollection).place(x=400, y=50)
        tk.Button(master, text='下载关注的画师图片', fg='black', command=self.mymember).place(x=400, y=100)
        # 图片id下载框
        tk.Label(master, text='输入图片id', font=('Arial', 12)).place(x=0, y=200)
        self.pid = tk.Entry(master, show=None)
        self.pid.place(x=100, y=200)
        tk.Button(master, text='下载', fg='black', command=self.getid).place(x=250, y=200)
        tk.Label(master, text='无需登录', font=('Arial', 12)).place(x=300, y=200)
        # 用户id下载框
        tk.Label(master, text='输入用户id', font=('Arial', 12)).place(x=0, y=250)
        self.uid = tk.Entry(master, show=None)
        self.uid.place(x=100, y=250)
        tk.Button(master, text='下载用户作品', fg='black', command=self.getuserwork).place(x=250, y=250)
        tk.Button(master, text='下载用户收藏', fg='black', command=self.getusercol).place(x=350, y=250)
        # 关键字下载框
        tk.Label(master, text='输入关键字', font=('Arial', 12)).place(x=0, y=300)
        self.kword = tk.Entry(master, show=None)
        self.kword.place(x=100, y=300)
        tk.Button(master, text='下载收藏大于5000', fg='black', command=self.getkey).place(x=250, y=300)

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
        rid = re.match('[1-9][0-9]{5,7}', id)
        if not rid:
            return self.evar.set('请输入正确的id')
        t = Thread(target=self.a.save_id, args=(id, True))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getuserwork(self):
        id = self.uid.get()
        usid = re.match('[1-9][0-9]{2,7}', id)
        if not usid:
            return self.eval.set('请输入正确的id')
        t = Thread(target=self.a.member_id, args=(id,))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getusercol(self):
        id = self.uid.get()
        usid = re.match('[1-9][0-9]{2,7}', id)
        if not usid:
            return self.eval.set('请输入正确的id')
        t = Thread(target=self.a.collection, args=(id,))
        t.start()
        return self.evar.set('下载中')

    @islogin
    def getkey(self):
        kword = self.kword.get()
        if not kword:
            return self.eval.set('关键字不能为空')
        t = Thread(target=self.a.word, args=(kword,))
        t.start()
        return self.evar.set('下载中')


# def save(dirpath):
#     frames = []
#     imglist = os.listdir(dirpath)
#     for img in imglist:
#         if os.path.exists(dirpath + img):
#             frames.append(Image.open(dirpath + img))
#     frames[0].save('imgs/1.gif', save_all=True, append_images=frames[1:], duration=1 / 24, format='GIF', loop=0)
def main():
    root = tk.Tk()
    root.title('下载')
    root.geometry('550x350')
    app = App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
