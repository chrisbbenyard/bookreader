# -*- coding: utf-8 -*-

import os
import urllib 
import re

# 使用新的版本的django
# from google.appengine.dist import use_library
# use_library('django', '1.1')

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue
from google.appengine.api import urlfetch

import BookParser
import Database
import Parser

def get_device_info(req):
  ua = req.headers['User-Agent']
  device_info = {}
  if ua.find('iPhone') != -1:
    device_info['device'] = 'iphone'
    device_info['template'] = 'iphone/'    
  else:
    device_info['device'] = 'desktop'
    device_info['template'] = 'template/'
  return device_info
  
  
def get_user_info(req):
  google_user = users.get_current_user()
  
  task_user = req.get('task_user')
  if len(task_user) == 0:
    task_user = None

  if req.cookies.has_key('user_key'):
    user_key = req.cookies['user_key']
    if (len(user_key) == 0) or user_key.find('@readtxt') == -1:
      user_key = None
  else:
    user_key = None
    
  user_info = {}

  if google_user:   
    user_info['username'] = google_user.email()
    user_info['logout_url'] = users.create_logout_url(req.uri) 
  elif task_user:    
    user_info['username'] = task_user
    user_info['logout_url'] = None
  elif user_key: 
    user_info['username'] = user_key
    user_info['logout_url'] = '/logout'
  else:
    user_info = None    
  
  # 如何用户没有“注册”（意思是不是Google账户，也不是从Login页面登录的User Key--从Login登录的都会记录）
  if user_info:
    user_info['user'] = Database.User.get_or_insert(
      'key:' + user_info['username'], 
      nickname = user_info['username'][:user_info['username'].find('@')],
      )
      
  return user_info
    
   
 
class Login(webapp.RequestHandler):
  def get(self):
    google_url = users.create_login_url('/')    # Google账户登录的URL
    template_values = {
      'google_url': google_url,
      }
    device_info = get_device_info(self.request)
    path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'login.html')
    self.response.out.write(template.render(path, template_values)) 
    
  def post(self):   # 用户使用User Key登录
    user_key = self.request.get('user_key').encode('utf-8')
    self.response.headers['Set-Cookie'] = 'user_key=' + user_key + "@readtxt"
    self.redirect('/')
    
    
    
class Logout(webapp.RequestHandler): # User Key注销
  def get(self):
    self.response.headers['Set-Cookie'] = 'user_key=anonymity' # 其实删除最好，但是不会，只要后面没有@readtxt就行
    self.redirect('/')  
    
    

    
    
class MainPage(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)   
    
    if user_info == None: 
      self.redirect('/login') 
      return   
    
    user = user_info['user']    
    # datetime使用str是为了包括和None比较的情况
    bookmarks = sorted( [bm.get_info() for bm in user.bookmarks], key = lambda x:x['update_date'], reverse = True)
    
    
    template_values = {
      'bookmarks': bookmarks,
      'logout_url': user_info['logout_url'], 
      'nickname': user.nickname,
      }
    device_info = get_device_info(self.request)
    path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'index.html')
    self.response.out.write(template.render(path, template_values))

# 用户信息
class UserInfo(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)
    if user_info == None: 
      self.redirect('/login') 
      return
    
    user = user_info['user']    
 
    template_values = {
      'nickname': user.nickname,
      'bookmark_number': len(user.get_user_bookmark_keys()),
      'book_number': len(user.get_user_book_keys()),
      'logout_url': user_info['logout_url'], 
      }
    device_info = get_device_info(self.request)
    path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'user.html')
    self.response.out.write(template.render(path, template_values))    
  
  def post(self):
    user_info = get_user_info(self.request)
    if user_info == None: 
      self.redirect('/login') 
      return
      
    user = user_info['user']
    nickname = self.request.get('nickname')
    user.nickname = nickname
    user.put()
    self.redirect('/user')
    
class AddBook(webapp.RequestHandler):
  def post(self, url = None):    
    user_info = get_user_info(self.request)    
    url = self.request.get('chapter_url')  

    result = task_add_book(user_info, url)
       
    if result:  # result不是None则有错误信息的字符串
      self.response.out.write(result)
      return
    
    self.redirect('/')
    
  def get(self, url):
    if not url:
      self.response.out.write('Error: Need url!')
      return 
    
    url = urllib.unquote(url)
    user_info = get_user_info(self.request)    
    result = task_add_book(user_info, url)
       
    if result != None: # result不是None
      self.response.out.write(result)
      return
    
    self.redirect('/')
    
class ManageBookmark(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)
    # 需要登录
    if user_info == None:
      self.redirect('/login') 
      return           
    
    user = user_info['user']    
    
    bookmarks = sorted( [bm.get_info() for bm in user.bookmarks], key = lambda x:x['title'])
    
    template_values = {
      'bookmarks': bookmarks,
      }

    path = os.path.join(os.path.dirname(__file__), 'template/bookmarks.html')
    self.response.out.write(template.render(path, template_values))
    
class DeleteBookmark(webapp.RequestHandler):
  def get(self, bookmark_id):
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) )   
    if bookmark != None:    
      # self.response.out.write(book.title + 'Deleted!')
      bookmark.delete()
      self.redirect('/bookmarks') 
    else:
      self.response.out.write('Error: ID does not exist!')
     
     
         
    

# 读的时候应该保证Chapter实例存在    
class ReadChapter(webapp.RequestHandler):
  def get(self, bookmark_id):
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) )             
    if bookmark == None:
      self.response.out.write('Error: Bookmark ID does not exist!')
      return
       
    chapter = task_get_chapter(bookmark.curr_url, bookmark.catalog_ref)
    if not isinstance(chapter, Database.Chapter): # 获取章节失败
      self.response.out.write(chapter)
      return
      
    template_values = {
      'chapter': chapter,
      'content': chapter.export_html(),
      'book': bookmark.get_info(),
      }
      
    device_info = get_device_info(self.request)
    path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'read.html')
    self.response.out.write(template.render(path, template_values))
 
 
class DownloadBook(webapp.RequestHandler):
  def get(self, bookmark_id):
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) )             
    if bookmark == None:
      self.response.out.write('Error: Bookmark ID does not exist!')
      return
      
    info = bookmark.get_info()
    catalog = bookmark.catalog_ref
    curr_index = catalog.chapter_url_list.index(bookmark.curr_url)  
    txt_content = ''
    for chapter_url in catalog.chapter_url_list[curr_index:]:           
      if chapter_url:
        chapter = task_get_chapter(chapter_url, catalog)
        if not isinstance(chapter, Database.Chapter): # 获取章节失败
            self.response.out.write(chapter)
   
        txt_content = txt_content + chapter.export_txt()
    
    # 设置header
    #print urllib.quote(info['title'].encode('utf-8'))
    self.response.headers['Content-Type'] = 'application/octet-stream;charset=utf-8' 
    self.response.headers['Content-Disposition'] = 'attachment;filename="' + urllib.quote(info['title'].encode('utf-8')) + '.txt"'

    self.response.out.write(txt_content)    
 
 
class SelectChapter(webapp.RequestHandler):
  def get(self, bookmark_id, chapter_url):
    if not chapter_url:
      self.response.out.write('Error: the URL does not exist!')      
      return
    else: 
      chapter_url = urllib.unquote(chapter_url)
      
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) )  
    if bookmark == None:        
      self.response.out.write('Error: Bookmark ID does not exist!')
      return

    bookmark.update_info(curr_url = chapter_url)        
  
    self.redirect('/bookmark/' + bookmark_id + '/read')
    
class LoadImage(webapp.RequestHandler):
  def get(self, bookmark_id, image_url):
    image_url = urllib.unquote(image_url)
      
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) )  
    if bookmark == None:        
      self.response.out.write('Error: Bookmark ID does not exist!')
      return
    
    fetch_result = urlfetch.fetch(image_url, 
                                  headers = {'Referer': bookmark.curr_url},
                                  allow_truncated = True)  
    image = fetch_result.content

    self.response.headers['Content-Type'] = "image/png"
    return self.response.out.write(image)


  

      

class BookmarkCatalog(webapp.RequestHandler):
  def get(self, bookmark_id):
      
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) ) 
    if not bookmark: 
      self.response.out.write('Error: ID does not exist!')
      return

    catalog = bookmark.catalog_ref

    # 如果还没读取目录，这是不对的
    if not catalog.chapter_url_list:
      self.response.out.write('Error: The catalog does not exist!')
      return

    template_values = {
      'book': bookmark.get_info(),
      'chapter_list': catalog.get_info()['chapter_list'],        
      }
    device_info = get_device_info(self.request)        
    path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'catalog.html')
    self.response.out.write(template.render(path, template_values))

      
      
      
      
class ManageBook(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)
    # 需要登录
    if user_info == None:
      self.redirect('/login') 
      return           
    
    user = user_info['user']    
   
    books = []
    for book in user.get_user_booklist():
      book_info = book.get_info()
      book_info['delete_link'] = '/book/delete/' + str(book.key())
      book_info['catalogs'] = []
      for catalog in book.catalogs: 
        catalog_info = catalog.get_info()  
        last_index = catalog.find_last_chapter_index()
        if last_index != None:
          catalog_info['last_chapter_url'] = catalog.chapter_url_prefix + catalog.chapter_url_list[last_index]
          catalog_info['last_chapter_title'] = catalog.chapter_title_list[last_index]
        catalog_info['chapter_number'] = catalog.get_chapter_number()
        last_check = Database.LastCheck.get_by_key_name(catalog_info['catalog_url'])
        if last_check:
          catalog_info['last_check_date'] = last_check.get_interval_format()
        else:
          catalog_info['last_check_date'] = ''
        book_info['catalogs'].append(catalog_info)
      books.append(book_info)
      
    template_values = {
      'booklist': books,
      }

    path = os.path.join(os.path.dirname(__file__), 'template/books.html')
    self.response.out.write(template.render(path, template_values))   

class DeleteBook(webapp.RequestHandler):
  def get(self, book_key_str):
    user_info = get_user_info(self.request)
    # 需要登录
    if user_info == None:
      self.redirect('/login') 
      return    
  
    user = user_info['user']
    book_key = Database.db.Key(encoded = book_key_str)
    book = Database.Book.get(book_key)  
    if book != None:    
      # self.response.out.write(book.title + 'Deleted!')
      for bookmark in user.bookmarks:
        if bookmark.book_ref.key() == book_key:
          bookmark.delete()
      
      self.redirect('/books') 
    else:
      self.response.out.write('Error: The book does not exist!')
     

      
    
class ExportList(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)
    # 需要登录
    if user_info == None:
      self.redirect('/login') 
      return           
      
    user = user_info['user']
 
    template_values = {
      'bookmarks': [bm for bm in user.bookmarks],
      }

    path = os.path.join(os.path.dirname(__file__), 'template/export.html')
    self.response.out.write(template.render(path, template_values))

    
    
        
class ImportList(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)
    # 需要登录
    if user_info == None:
      self.redirect('/login') 
      return           
    
    template_values = { }

    path = os.path.join(os.path.dirname(__file__), 'template/import.html')
    self.response.out.write(template.render(path, template_values))   

    
  def post(self):    
    user_info = get_user_info(self.request)
    
    if user_info == None:
      self.redirect('/login') 
      return            
    
    content = self.request.get('import_content')
 
    url_list_re = re.compile(r'(http\S*)')
    url_list = url_list_re.findall(content)
    for url in url_list:
      taskqueue.add(url='/task/addbook', params={'url': url, 
                                                 'task_user': user_info['username']})
    
    self.redirect('/bookmarks')
    
    
    
    
# 由用户发出的要求，所以不等计划任务，立即更新   
class QuickUpdate(webapp.RequestHandler):
  def get(self):
    user_info = get_user_info(self.request)
    # 需要登录
    if user_info == None:
      self.redirect('/login') 
      return           
    
    user = user_info['user']
    
    catalog_set = set()        
    for bm in user.bookmarks:
      if (bm.next_url==None) and (not bm.catalog_url in catalog_set):
        taskqueue.add(url='/task/update', params={'catalog_url': bm.catalog_url})
        catalog_set.add(bm.catalog_url)
        
    self.redirect('/')

class Help(webapp.RequestHandler):
  def get(self):    
    parser_info = Parser.get_parser_info()

    template_values = {
      'parser_info': parser_info,      
      }
    device_info = get_device_info(self.request)    
    path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'help.html')
    self.response.out.write(template.render(path, template_values))   

   
   
   

     
     
     
     
class UpdateBook(webapp.RequestHandler):
    
  def get(self, bookmark_id, op=None):     
      
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) )   
    
    if bookmark != None:         
      if op == None: # 显示页面
        bookmark_info = bookmark.get_info()
        catalog = bookmark.catalog_ref
        catalog_info = {}
        last_index = catalog.find_last_chapter_index()
        if last_index != None:
          catalog_info['last_url'] = catalog.chapter_url_prefix + catalog.chapter_url_list[last_index]
          catalog_info['last_title'] = catalog.chapter_title_list[last_index]
        catalog_info['chapter_number'] = catalog.get_chapter_number()
        catalog_info['not_download_number'] = len(catalog.get_not_downloaded_chapter_list())
        last_check = Database.LastCheck.get_by_key_name(bookmark.catalog_url)
        if last_check:
          catalog_info['last_check_date'] = last_check.get_interval_format()
        else:
          catalog_info['last_check_date'] = ''
        template_values = {
          'book': bookmark_info,  
          'catalog': catalog_info,
          }
        device_info = get_device_info(self.request)
        path = os.path.join(os.path.dirname(__file__), device_info['template'] + 'update.html')
        self.response.out.write(template.render(path, template_values))
      
      elif op == 'manual': # 手动更新          
        catalog = bookmark.catalog_ref
        result = task_update_catalog(catalog)            
        self.redirect('/bookmark/' + bookmark_id + '/update')
        return
      
      elif op == 'reload': # 更新当前章节
        task_get_chapter(bookmark.curr_url, bookmark.catalog_ref, reload = True)
        self.redirect('/bookmark/' + bookmark_id + '/read')
        return 
      
      elif op == 'fetch': # 获取全部章节
        catalog = bookmark.catalog_ref
        catalog_url = catalog.key().name()          
        for chapter_url in catalog.chapter_url_list:
          if chapter_url:
            taskqueue.add(url='/task/chapter', params={'catalog_url': catalog_url,
                                                       'chapter_url': chapter_url})
        self.redirect('/bookmark/' + bookmark_id + '/update')
        return 

      else: # 指定网址更新，catalog是可知的
        self.response.out.write('Error: Unknown operation: ' + op + '.')
        return
        
    else:
      self.response.out.write('Error: ID does not exist!')

  # 这个功能本来想取消，后来用这种变通的方案，会改变bookmark的ID，因为不是一个了
  def post(self, bookmark_id):
    bookmark = Database.Bookmark.get_by_id( int(bookmark_id) ) 
    user_info = get_user_info(self.request)
    
    url = self.request.get('chapter_url')

    result = task_add_book(user_info, url)
       
    if result: # result不是None
      self.response.out.write(result)
      return
    
    bookmark.delete()
    self.redirect('/bookmarks')

      

# task_ 为前缀的函数不进行任何判断，直接执行
def task_add_book(user_info, url):
  if user_info == None:      
    return 'Error: User is not correct!'

  user = user_info['user']
  
  (book_info, parser) = BookParser.get_parser(url)

  if book_info == None:
    return 'Error: URL is not supported!'
  
  url_type = book_info['url_type']
  
  # 首先加入书页信息，获取必备的数据
  if book_info['cover_url']:
    book_info.update( BookParser.get_data(book_info['cover_url']) )
  
  # 必须有作者，标题，目录页，章节地址前缀
  # 如果没有这些就没法构造 Book 和 Catalog
  if not ( book_info.has_key('author') and 
           book_info.has_key('title') and 
           book_info.has_key('catalog_url') and 
           book_info.has_key('chapter_url_prefix') ):      
    return 'Error: The necessary information is not complete!' + '<br />' + str(book_info)
  author = book_info['author']
  title = book_info['title']
  catalog_url = book_info['catalog_url']
 

  # Book
  book_key_name = Database.generate_book_key_name(author, title)    
  book = Database.Book.get_or_insert(book_key_name)  
    
  # Catalog
  catalog_key_name = catalog_url
  catalog = Database.Catalog.get_or_insert(catalog_key_name, book_ref = book)
  last_check = Database.LastCheck.get_or_insert(catalog_url)
  # 判断是否需要重新获取目录
  if not book_info['last_url'] in catalog.chapter_url_list:    # 包括了catalog 是新生成的，即使last_url是None
    # 获取目录
    book_info.update( BookParser.get_data(catalog_url) )
    catalog.put_info(book_info)     
    last_check.put()
    
  # 用户想要添加的章节
  curr_url = None
  # 具体章节
  if url_type == 'chapter':     
    curr_url = url
  # 书页
  elif url_type == 'cover':       
    if book_info.has_key('last_url'):
      curr_url = book_info['last_url']
  # 目录
  elif url_type == 'catalog':
    curr_index = catalog.find_first_chapter_index()
    if curr_index != None:
      curr_url = catalog.chapter_url_list[curr_index]
   
  bookmark = Database.Bookmark(user_ref = user, book_ref = book, catalog_ref = catalog)
  bookmark.update_info( user_ref = user, book_ref = book, catalog_ref = catalog, curr_url = curr_url)
  
  
# 保证获取一个完整的章节
# 如果没有内容则获取
# 成功返回实例，失败返回字符串(str or unicode)
def task_get_chapter(url, catalog, reload = False):
  if not url in catalog.chapter_url_list:
    return 'Error: The url does not exist!'
  
  
  chapter_url = catalog.chapter_url_prefix + url  
  chapter = Database.Chapter.get_or_insert(chapter_url, catalog_ref = catalog)
  
  if chapter:
    if reload or (not chapter.content_list): 
      chapter_info = BookParser.get_data(chapter_url)
      chapter.put_info(chapter_info)
    return chapter
  else:
    return "Error: Can't get the chapter!"
 


# 如果更新了返回 Ture
# 依据目录是否一致来判断
def task_update_catalog(catalog):
  catalog_url = catalog.key().name()
  last_check = Database.LastCheck.get_by_key_name(catalog_url)
  
  if last_check:
    if last_check.is_more_minutes(10):
      last_check.put()
    else:
      return False        
  else:
    last_check = Database.LastCheck.get_or_insert(catalog_url)
  # 开始更新
  new_catalog_info = BookParser.get_data(catalog_url)
  if (new_catalog_info['chapter_url_list'] != catalog.chapter_url_list) and (len(new_catalog_info['chapter_url_list'])>0):
    # 更新最后更新时间
    new_catalog_info.update( BookParser.get_data(catalog.cover_url) )
    catalog.put_info(new_catalog_info)
    catalog.update_bookmarks()
    return True
  else:
    return False


  
class TaskQueue(webapp.RequestHandler):   
  def post(self, method):
    retry_count = int(self.request.headers.get('X-AppEngine-TaskRetryCount', 0)) 
    if retry_count > 12:
      return
    if method == 'addbook':
      url = self.request.get('url')    
      user_info = get_user_info(self.request)
      task_add_book(user_info, url)
    if method == 'update':
      catalog_url = self.request.get('catalog_url')
      catalog = Database.Catalog.get_by_key_name(catalog_url)
      if catalog:
        result = task_update_catalog(catalog)
        if result: # 目录更新了，预读一下后五章
          for chapter_url in catalog.chapter_url_list[-5:]:
            if chapter_url:
              taskqueue.add(url='/task/chapter', params={'catalog_url': catalog.key().name(),
                                                         'chapter_url': chapter_url})
    if method == 'chapter':
      catalog_url = self.request.get('catalog_url')
      chapter_url = self.request.get('chapter_url')
      catalog = Database.Catalog.get_by_key_name(catalog_url)
      if catalog and chapter_url:
        task_get_chapter(chapter_url, catalog)
        
class Schedule(webapp.RequestHandler):
  def get(self, method):
    if method == 'update':
      catalog_list = Database.Catalog.all()
      for catalog in catalog_list:     
        taskqueue.add(url='/task/update', params={'catalog_url': catalog.key().name()})




# 实现Atom推送，以cover_url为参数   
# 注意，网址都是小写！因为我在 BookParser 中都小写处理了   
class Atom(webapp.RequestHandler):
  # def head(self, catalog_url):
    # user_agent = self.request.headers.get('User-Agent')
    # if user_agent.find('Feedfetcher-Google') != -1:
      # self.response.set_status(301)
      # self.response.headers.add_header("Location", 'http://feed.appinn.com/')
    # return 
    
  def get(self, catalog_url):
    user_agent = self.request.headers.get('User-Agent')
    
    # 不允许其他Bot，只允许我设置的GAE服务器
    if user_agent.find('AppEngine-Google') == -1:
      self.error(404)
      return
        
    catalog_url = urllib.unquote(catalog_url)

    catalog = Database.Catalog.get_by_key_name(catalog_url)
    if not catalog:
      self.error(410)      
      return 
    
    task_update_catalog(catalog)
    book = catalog.book_ref
    
    url_list = catalog.chapter_url_list
 
    url_list.sort()
    url_list = url_list[-5:] # 只抓取5篇，否则Google也不要
    url_list.reverse()  
    chapter_list = []
    for url in url_list:
      chapter = task_get_chapter(url, catalog)
      if isinstance(chapter, Database.Chapter):
        chapter_list.append(chapter.get_info())  
      
    template_values = {
      'last_update_date': Database.LastCheck.get_or_insert(catalog_url).last_check_date.isoformat(),
      'book': book,
      'catalog': catalog.get_info(),
      'chapter_list': chapter_list,
      'content': chapter_list[0]['content']
      }
    path = os.path.join(os.path.dirname(__file__), 'template/atom.xml')
    self.response.out.write(template.render(path, template_values))
  

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/login', Login),
                                      ('/logout', Logout),
                                      ('/user', UserInfo),
                                      ('/export', ExportList),
                                      ('/import', ImportList),
                                      ('/quickupdate', QuickUpdate),
                                      (r'/addbook/(.*)', AddBook),
                                      
                                      ('/bookmarks', ManageBookmark),
                                      (r'/bookmark/([^/]*)/read', ReadChapter),
                                      (r'/bookmark/([^/]*)/img/(.*)', LoadImage),                                      
                                      (r'/bookmark/([^/]*)/update', UpdateBook),
                                      (r'/bookmark/([^/]*)/update/(.*)', UpdateBook),
                                      (r'/bookmark/([^/]*)/delete', DeleteBookmark),
                                      (r'/bookmark/([^/]*)/catalog', BookmarkCatalog),
                                      (r'/bookmark/([^/]*)/select/(.*)', SelectChapter),
                                      (r'/bookmark/([^/]*)/download', DownloadBook),
                                      
                                      ('/books', ManageBook),
                                      (r'/book/delete/(.*)', DeleteBook), 

                                      (r'/task/(.*)', TaskQueue),
                                      (r'/cron/(.*)', Schedule),
                                      (r'/atom/(.*).xml', Atom), # 因为Google Reader不接受Feed以html结尾
                                      
                                      ('/help', Help),
                                      ],
                                     debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()