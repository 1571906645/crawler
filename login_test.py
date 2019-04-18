import requests
import re
from bs4 import BeautifulSoup
import os
import zipfile
from PIL import Image
import threading


# import imageio


class user(object):
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

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.userid = self.login()

    # 模拟登录
    def login(self):
        loginkey = self.psession.get('https://accounts.pixiv.net/login', headers=self.header)
        post_key = re.search('name="post_key".*?value="(.*?)"', loginkey.text).group(1)
        postdata = {
            'password': self.password,
            'pixiv_id': self.username,
            'post_key': post_key,
        }
        login_response = self.psession.post(self.posturl, headers=self.header, data=postdata)
        userresponse = self.psession.get(self.baseurl, headers=self.header)
        userid = re.search('\[\{.*?user_id: "(\d+)".*?\}\]', userresponse.text).group(1)
        return userid

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
            self.save_id(id=id)

    # 保存收藏id
    def collection(self):
        bookmarks_url = 'https://www.pixiv.net/ajax/user/%s/illusts/bookmarks?tag=&offset=0&limit=9999&rest=show' % self.userid
        colresponse = self.psession.get(bookmarks_url, headers=self.header).json()
        # idlist = [i['id'] for i in colresponse['body']['works']]
        for i in colresponse['body']['works']:
            self.save_id(id=i['id'], favorites=True)

    # 根据作品id得到图片url和Referer
    def save_id(self, id=73598112, favorites=None):
        id_url = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(id)
        more_url = 'https://www.pixiv.net/member_illust.php?mode=manga&illust_id=' + str(id)
        id_ajax = 'https://www.pixiv.net/ajax/illust/' + str(id)
        idresponse = self.psession.get(id_ajax, headers=self.header)
        img = idresponse.json()['body']['urls']['original']
        imgnum = idresponse.json()['body']['pageCount']
        imgtype = idresponse.json()['body']['illustType']
        if favorites:
            filepath = 'Author/%s/' % self.userid
        else:
            title = idresponse.json()['body']['userName']
            filepath = 'Author/' + title + '/'
        if not os.path.exists(filepath):
            os.makedirs(filepath)
        if imgnum > 1:
            for i in range(0, imgnum):
                newimg = img.replace('_p0', '_p' + str(i))
                self.save_file(url=id_url, img=newimg, filename=filepath)
        else:
            self.save_file(url=id_url, img=img, filename=filepath)
        if imgtype == 2:
            self.save_gif(id=id, idpath=filepath)

    # 保存图片
    def save_file(self, url, img, filename):
        save_headers = {
            'Referer': url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
        }
        name = img.split('/')[-1]
        if os.path.isfile(filename + name):
            return print(name + '已存在')
        res = self.downloadsession.get(img, headers=save_headers)
        if res.status_code == 200:
            with open(filename + name, 'wb') as f:
                f.write(res.content)
                f.close()
        return print(name)

    # 保存动图
    def save_gif(self, id, idpath):
        if os.path.isfile(idpath + str(id) + '.gif'):
            return print(id + '已存在')
        href = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + str(id)
        headers = {
            'Referer': href,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
        }
        res = requests.get(href, headers=headers)
        urls = re.findall('"(https://i\.pximg\..*?' + str(id) + '.*?)"', res.text)
        url = urls[-1]
        zurl = url.replace('c/128x128/img-master', 'img-zip-ugoira').replace('square1200.jpg', 'ugoira1920x1080.zip')
        zzurl = zurl.replace('1920x1080', '600x600')
        dirpath = 'Iimgs/' + str(id) + '/'
        response = requests.get(zurl, headers=headers)
        if response.status_code == 200:
            print(zurl)
            name = zurl.split('/')[-1]
            with open('Iimgs/' + name, 'wb') as f:
                f.write(response.content)
                f.close()
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            zf = zipfile.ZipFile('Iimgs/' + name, 'r')
            for file in zf.namelist():
                zf.extract(file, dirpath)
            zf.close()
            # self.imgname(dirpath)
            frames = []
            imglist = os.listdir(dirpath)
            for img in imglist:
                if os.path.exists(dirpath + img):
                    frames.append(Image.open(dirpath + img))
            frames[0].save(idpath + str(id) + '.gif', save_all=True, append_images=frames, duration=1 / 24)
            del frames
            # os.system('ffmpeg -r 24 -i ' + dirpath + '%d.jpg ' + idpath + str(id) + '.gif')
            self.del_file(dirpath)
            os.remove('Iimgs/' + name)
            response.close()
            return print('%s-gif' % id)

    # 清理解压内容
    def del_file(self, path):
        ls = os.listdir(path)
        for i in ls:
            d_path = os.path.join(path, i)
            if os.path.isdir(d_path):
                self.del_file(d_path)
            else:
                os.remove(d_path)

    # 重命名解压文件
    def imgname(self, path):
        dirs = os.listdir(path)
        for img in dirs:
            img_path = os.path.join(path, img)
            while img.startswith('0') and len(img) >= 6:
                img = img[1:]
            newpath = os.path.join(path, img)
            os.rename(img_path, newpath)

    def author(self):
        self.member()
        self.id_set.remove('11')
        print(self.id_set)
        threads = []
        for m_id in self.id_set:
            t = threading.Thread(target=self.member_id, args=(m_id,))
            threads.append(t)
        threadnum = len(threads)
        for i in range(threadnum):
            threads[i].start()
        for i in range(threadnum):
            threads[i].join()


if __name__ == '__main__':
    a = user('用户名', '密码')
    # print(a.userid)
    # a.collection()
    # a.author()
    # save_gif(id=73315187, idpath='Author/')
