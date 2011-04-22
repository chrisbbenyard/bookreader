# -*- coding: utf-8 -*-

from google.appengine.ext import db
import datetime




#-----------------
# 数据库分为两种
#     一种是数据源，比如Book，Catalog，Chapter等
#     一种需要别的数据库提供数据，比如Bookmark，这种数据库只是作为缓存，避免频繁对Datastore进行操作。
# 因此，原始数据有get_info和put_info，第二类数据有get_info和update_info
# Bookmark 和 Chapter 可直接删除
#-----------------



# 用户信息
# key_name = key:[username] # 创建者
class User(db.Model):    
  nickname = db.TextProperty() # 昵称
  tz_info = db.TextProperty(default = 'GMT+8') # 时区信息
    
  # 获取的是key列表
  def get_user_bookmark_keys(self):
    return [key for key in Bookmark.all(keys_only=True).filter('user_ref =', self)]
  
  # 获取的是key列表
  def get_user_book_keys(self):
    key_set = set()
    for bm in self.bookmarks:
      book_key = Bookmark.book_ref.get_value_for_datastore(bm)
      key_set.add(book_key)
    return list(key_set) 
  
  def get_user_booklist(self):
    return db.get( self.get_user_book_keys() )
  
  def delete_with_bookmarks(self):
    db.delete( self.get_user_bookmark_keys() )
    self.delete()
    
def generate_user_key_name(username):
  return 'key:' + username

def resolve_user_key_name(keyname):
  username = keyname[4:]
  return username
  


    
# 书籍数据
# key_name = key:[作者]|[书名]
# Book - Part - Chapter - Section
# 保存书的基本信息，是书的抽象概念，不涉及到网站一类的
# user_ref 是为了社会化功能
class Book(db.Model):
  #user_ref = db.ReferenceProperty(User, collection_name='books', required=True)

  #info = db.TextProperty() # 书的简介
  
  def get_info(self):
    (author, title) = resolve_book_key_name(self.key().name())
    return {
      'author': author,
      'title': title}  
  

def generate_book_key_name(author, title):
  return 'key:' + author + '|' + title

def resolve_book_key_name(keyname):
  s = keyname[4:].split('|')
  author = s[0]
  title = s[1]
  return (author, title) 
  






  
# 目录结构管理
# 一本书可以有多个目录，至于多个网站之间怎么匹配，在这一层完成
# 这样设计也是由网络小说的特点决定的（多个盗贴站更新）
# key_name = [catalog_url] # 目录页
class Catalog(db.Model):
  book_ref = db.ReferenceProperty(Book, collection_name = 'catalogs', required=True)
  
  site = db.TextProperty() # 站点名称(通常是简称，显示给读者看的)  
  cover_url = db.TextProperty()	# 书页  
  
  chapter_url_prefix = db.TextProperty() # 章节URL列表中保持的是末尾部分，前面相同的保存为前缀
  chapter_url_list = db.ListProperty(db.Text) # 目录的链接列表，如果为空串，则表示为Part分割   
  chapter_title_list = db.ListProperty(db.Text) # 目录的章节名称列表
  
  update_date = db.DateTimeProperty() # 更新日期
 
  def put_info(self, info):    
    if info.has_key('site'):
      self.site = info['site']
    if info.has_key('cover_url'):
      self.cover_url = info['cover_url']
    if info.has_key('chapter_url_list'):
      self.chapter_url_list = [db.Text(x.strip()) for x in info['chapter_url_list']]
    if info.has_key('chapter_title_list'):
      self.chapter_title_list = [db.Text(x.strip()) for x in info['chapter_title_list']]
    if info.has_key('chapter_url_prefix'):
      self.chapter_url_prefix = info['chapter_url_prefix']
    if info.has_key('update_date'):
      self.update_date = info['update_date']
    
    self.put()
      
  def get_info(self):
    return {
      'site': self.site,
      'cover_url': self.cover_url,
      'update_date': self.update_date,
      'catalog_url': self.key().name(),
      'chapter_list': [ {'url': self.chapter_url_list[i], 'title': self.chapter_title_list[i]}
                        for i in range(len(self.chapter_url_list))]
      }
    
  def update_bookmarks(self):
    # 统一 put
    bm_list = []
    for bm in self.bookmarks:
      bm.update_info(catalog_ref = self, do_put = False)
      bm_list.append(bm)
    db.put(bm_list)
        
  def find_next_chapter(self, curr_index):
    next_index = curr_index + 1
    while next_index < len(self.chapter_url_list):
      if self.chapter_url_list[next_index]: # 不是空串
        return self.chapter_url_list[next_index]
      next_index = next_index + 1
    return None  
    
  def find_prev_chapter(self, curr_index):
    prev_index = curr_index - 1
    while prev_index >= 0:
      if self.chapter_url_list[prev_index]: # 不是空串
        return self.chapter_url_list[prev_index]
      prev_index = prev_index - 1
    return None       
   
  def find_first_chapter_index(self):
    i = 0
    while i < len(self.chapter_url_list):
      if self.chapter_url_list[i]:
        return i
      i = i + 1
    return None

  def find_last_chapter_index(self):
    i = len(self.chapter_url_list) - 1
    while i >= 0:
      if self.chapter_url_list[i]:
        return i
      i = i - 1
    return None
    
  def get_chapter_number(self):
    chapter_list = [x for x in self.chapter_url_list if x] # 非空串就是实际的章节，空串是分卷名
    return len(chapter_list)
  
  def get_not_downloaded_chapter_list(self):
    chapter_list = []
    for url in self.chapter_url_list:
      if url:
        chapter_url = self.chapter_url_prefix + url
        chapter = Chapter.get_by_key_name(chapter_url)
        if (not chapter) or (chapter.content_type != 'text'):
          chapter_list.append(chapter_url)
    return chapter_list
          

   
  def get_related_chapter_keys(self):
    return [key for key in Chapter.all(keys_only=True).filter('catalog_ref =', self)] 

  def get_related_bookmark_keys(self):
    return [key for key in Bookmark.all(keys_only=True).filter('catalog_ref =', self)]     
    
  def delete_with_chapters_and_bookmarks(self):
    related_chapters = self.get_related_chapter_keys()
    related_bookmarks = self.get_related_bookmark_keys()
    # 每次删除500个
    while related_bookmarks:        
        db.delete(related_bookmarks[0:500]) 
        related_bookmarks = related_bookmarks[500:]
    while related_chapters:
        db.delete(related_chapters[0:500])
        related_chapters = related_chapters[500:]
    self.delete()
    
  def get_user_nicknames(self):
    return set([bm.user_ref.nickname for bm in self.bookmarks])









    
# 章节数据
# key_name = [具体的URL] 	# 当前章节
# 如果用 Catalog 中的章节顺序，则保证作者在插入到前面的时候还能看
# 如果用 Chapter 中的上下章的顺序，则作者在插入后就不知道了，但应该能保证阅读
# 我认为，没有下一章的Chapter肯定在Catalog 的List最后（但不一定是数字最大的，因为可能是作者的通知）
# 一般作者也就在正文最前面插入，所以不会影响阅读，这两个顺序用哪个都行
# 但是如果一直用 Chapter 自带的上下章链接 则很容易造成死链，而且不知道是否更新
#（虽然可以保存一个无下章的列表，但是还是不太好）
# 如果一个用户很早就添加了这本书，然后不看，则这时候这个链接就很难追踪更新
class Chapter(db.Model):
  catalog_ref = db.ReferenceProperty(Catalog, collection_name = 'chapters', required=True)

  content_type = db.TextProperty() # 章节类型(text,image,none)
  content_list = db.ListProperty(db.Text) # 章节内容（每段为一个单位，以后为了图片列表）
  chapter_title = db.TextProperty() # 章节标题，这个标题可能包含第几卷的卷名，和Catalog里面的有所不同
  
  def put_info(self, info): 
    if info.has_key('content_list'):  
      self.content_list = [ db.Text(x) for x in info['content_list'] ]
    if info.has_key('chapter_title'): 
      self.chapter_title = info['chapter_title'] 
    if info.has_key('content_type'):
      self.content_type = info['content_type']
    self.put()
    
      
  def get_info(self):    
    return {
      'chapter_title': self.chapter_title,
      'content': self.export_html(),
      'curr_url': self.key().name(), 
      }    

  def export_html(self):
    return ''.join( [u'<p>　　'+x+'</p>' for x in self.content_list] )
    
  def export_txt(self):
    return self.chapter_title + '\r\n' + ''.join( [u'\r\n　　'+x+'\r\n' for x in self.content_list] ) + '\r\n\r\n'
    

# 用户书签
# 使用自动生成的ID
# 因为本类大部分数据是靠引用得到的，所以都备份一份虽然占用一点空间，但是速度快
class Bookmark(db.Model):
  # user_ref 必须有，且不能更改，在构造的时候直接赋值
  user_ref = db.ReferenceProperty(User, collection_name='bookmarks', required=True)
  # 下面的可选 None
  book_ref = db.ReferenceProperty(Book, collection_name = 'bookmarks', required=True)
  catalog_ref = db.ReferenceProperty(Catalog, collection_name = 'bookmarks', required=True)  
  #chapter_ref = db.ReferenceProperty(Chapter, collection_name = 'bookmarks') # 当前章节的引用
  
  add_date = db.DateTimeProperty(auto_now_add=True)	# 加入时间
  modified_date = db.DateTimeProperty(auto_now=True) # 最后刷新日期
  
  curr_url = db.TextProperty()
  
  # 下面这些属性虽然可以从引用中得到，为了速度保存于此
  # 基本属性，除非实例更新，否则也不更新
  # from user
  tz_info = db.TextProperty()
  # from book
  title = db.TextProperty()
  author = db.TextProperty()  
  # from catalog
  site = db.TextProperty()
  cover_url = db.TextProperty()
  chapter_url_prefix = db.TextProperty()
  catalog_url = db.TextProperty()
  update_date = db.DateTimeProperty()  
  # form curr_url & catalog
  chapter_title = db.TextProperty()  
  next_url = db.TextProperty()
  prev_url = db.TextProperty()
  #curr_index = db.IntegerProperty()
  
    
  # 本函数只会更新用户指定的部分
  # do_put 是询问是否立即put()，如果设置为False，则可以保存到列表中一起Put
  def update_info(self, 
                  user_ref = None, book_ref = None, catalog_ref = None,
                  curr_url = None,
                  do_put = True):
    if user_ref:
      self.user_ref = user_ref
      self.tz_info = user_ref.tz_info
      
    if book_ref:
      self.book_ref = book_ref
      (self.author, self.title) = resolve_book_key_name(book_ref.key().name())
      
    if catalog_ref:
      self.catalog_ref = catalog_ref   
      self.site = catalog_ref.site
      self.catalog_url = catalog_ref.key().name()
      self.cover_url = catalog_ref.cover_url 
      self.chapter_url_prefix = catalog_ref.chapter_url_prefix
      self.update_date = catalog_ref.update_date
      
    if curr_url:
      if curr_url.find('http://') == 0:      
        self.curr_url = curr_url[ curr_url.rfind('/')+1 : ] # 注意 即使rfind找不到返回-1也对
      else:
        self.curr_url = curr_url

    if curr_url or catalog_ref:
      url = self.curr_url
      catalog = self.catalog_ref
      try:       
        curr_index = catalog.chapter_url_list.index(url)      
        self.chapter_title = catalog.chapter_title_list[curr_index]
        self.next_url = catalog.find_next_chapter(curr_index)
        self.prev_url = catalog.find_prev_chapter(curr_index)
        
      except: # 非法当前章节（至少现在的目录里面没有）
        print 'Error'
        print url
        self.curr_url = None
        self.chapter_title = None
        self.next_url = None
        self.prev_url = None     
    
    if do_put:  
      self.put()
    
  def get_info(self):    
    if self.tz_info == 'GMT+8':
      time_delta = +8
    else:
      time_delta = 0
    info = {
      'site': self.site,
      'title': self.title,
      'author': self.author,
      'chapter_title': self.chapter_title,      
      'curr_url': self.curr_url,
      'next_url': self.next_url,
      'prev_url': self.prev_url, 
      'cover_url': self.cover_url,
      'catalog_url': self.catalog_url,
      'update_date': self.update_date + datetime.timedelta(hours=time_delta),
      'add_date': self.add_date + datetime.timedelta(hours=time_delta),
      'modified_date': self.modified_date + datetime.timedelta(hours=time_delta),
      }
    id = str(self.key().id())
    info['read_link'] = '/bookmark/read/' + id
    info['select_link'] = '/bookmark/select/' + id + '/'
    if self.next_url:
      info['next_link'] = info['select_link'] + self.next_url
    else:
      info['next_link'] = None
    if self.prev_url:
      info['prev_link'] = info['select_link'] + self.prev_url
    else:
      info['prev_link'] = None 
      
    info['update_link'] = '/bookmark/update/' + id
    info['delete_link'] = '/bookmark/delete/' + id
    info['catalog_link'] = '/bookmark/catalog/' + id
    info['download_link'] = '/bookmark/download/' + id
    
    return info





    
# key_name = [url]
# 最后一次检查的时间      
class LastCheck(db.Model):
  last_check_date = db.DateTimeProperty(auto_now = True)
  
  def get_interval(self):
    return datetime.datetime.utcnow() - self.last_check_date
    
  def get_interval_format(self):
    interval = self.get_interval()
    hour = interval.days*24 + interval.seconds/3600
    minute = (interval.seconds % 3600) / 60
    second = interval.seconds % 60
    if hour != 0:
      return u'%d时%d分%d秒' % (hour, minute, second)
    elif minute !=0:
      return u'%d分%d秒' % (minute, second)
    else:
      return u'%d秒' % (second)
      
  
  def is_more_minutes(self, minutes):
    return self.get_interval() > datetime.timedelta(minutes = minutes)