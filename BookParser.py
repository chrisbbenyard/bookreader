# -*- coding: utf-8 -*-

from google.appengine.api import urlfetch
from BSXPath import BSXPathEvaluator,XPathResult
from BeautifulSoup import BeautifulSoup

import re
import datetime

#debug
#import urllib2

def get_xpath_string(document, xpath):
  try:
    return unicode(document.getFirstItem(xpath).string).strip('\r\n ')
  except:
    return None

def get_xpath_contents(document, xpath):
  try:
    return u''.join( [unicode(x) for x in document.getFirstItem(xpath).contents] )
  except:
    return None    
    
def get_xpath_unicode(document, xpath):
  try:
    return unicode(document.getFirstItem(xpath)).strip('\r\n ')
  except:
    return None
  
def get_xpath_attr(document, xpath, attr):
  try:
    return ((document.getFirstItem(xpath))[attr]).strip('\r\n ')
  except:
    return None
    
def get_re_first(html, r):
  if html:    
    result = r.findall(html)
    if len(result) > 0:
      return result[0]
  
  return None

def get_re_last(html, r):
  if html:    
    result = r.findall(html)
    if len(result) > 0:
      return result[-1]
  
  return None

# None 和空串不放入字典
# 注意到，如果value是空一类的值，则不要添加到字典
# 因为有可能当前key可以通过别的方式获得，如果赋成了None则会冲掉正确值
# 不过，有的变量必须赋值为None，比如上下章链接，这个在get_data中处理
def put_into_dict(d, key, value):
  if (value != None) and (value != ''):
    d[key] = value
    

    
  
def qidian_parse_book(book_url): 
  main_read_url = 'http://www.qidian.com/BookReader/'

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  title_div = document.find('div','title')
  put_into_dict(parse_result, 'title', unicode(title_div.h1.string).strip('\r\n '))
  put_into_dict(parse_result, 'author', unicode(title_div.a.string).strip('\r\n '))

  # 起点这里可能有两个时间，第一个就是公众更新时间，第二个是VIP时间
  # 我应该获取后一个时间（如果有2个，则获取VIP更新）   
  update_date_html = unicode(document.find('div','tabs'))  
  if update_date_html:
    update_date_re = re.compile(u'\s*(\d*)-(\d*)-(\d*)\s*(\d*):(\d*)') 
    update_date = get_re_last(update_date_html, update_date_re)
    if update_date:
      (year, month, day, hour, minute) = update_date
      put_into_dict(parse_result, 'update_date', 
        datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), 0) + datetime.timedelta(hours=-8))  
    
  last_url_xpath = '//*[@id="readP"]'
  last_url = document.getFirstItem(last_url_xpath).div.h3.a['href']
  if last_url:    
    put_into_dict(parse_result, 'last_url', last_url[ last_url.rfind('/') + 1 : ])  # 截取最后一部分    
    put_into_dict(parse_result, 'chapter_url_prefix', main_read_url)
  
  return parse_result
  

def qidian_parse_chapter(chapter_url):
  main_url = 'http://www.qidian.com'
  main_read_url = 'http://www.qidian.com/BookReader/'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
 
  chapter_title_xpath = '//*[@id="lbChapterName"]'
  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, chapter_title_xpath))

  
  content_xpath = '/html/body/form/div[3]/div/div/div[2]/div[2]/script'
  content_link = get_xpath_attr(document, content_xpath, 'src')
  if content_link:
    chapter_content = urlfetch.fetch(content_link, allow_truncated=True).content.decode('gbk', 'ignore')  
    end_pos = chapter_content.rfind("');")
    chapter_content = chapter_content[ 16:end_pos ]  # 去掉 document.write
    for repeat in range(2): # 竟然可能出现两遍，http://www.qidian.com/BookReader/1440558,26722994.aspx
      end_pos = chapter_content.rfind("<a href=http://www.qidian.com>")
      if end_pos != -1:
        chapter_content = chapter_content[0:end_pos] # 去掉页末的链接
    end_pos = chapter_content.rfind("<a href=http://www.cmfu.com>")
    if end_pos != -1:
      chapter_content = chapter_content[0:end_pos] # 去掉页末的链接  
      
    # 开始格式化文本
    chapter_content = chapter_content.rstrip(u'　') # 去掉末尾的全角空格
    paragraph_list = chapter_content.split('<p>')
    paragraph_list = [x for x in paragraph_list if x.strip()]
    put_into_dict(parse_result, 'content_list', paragraph_list)
    put_into_dict(parse_result, 'content_type', 'text')
    
  return parse_result

def qidian_parse_catalog(catalog_url):
  #main_read_url = 'http://www.qidian.com/BookReader/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)  

  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}
  
  #title_xpath = '/html/body/form/center/b/h1'
  #put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  
  list_xpath = '//*[@id="bigcontbox"]'
  document = document.getFirstItem(list_xpath)
  
  if not document:
    return
  
  vol_list = document.findAll('div', 'box_title')
  ul_list = document.findAll('div', 'box_cont')

  chapter_url_list = []
  chapter_title_list = []
  for i in range(len(vol_list)):    
    title = vol_list[i].find('b')
    chapter_url_list.append('') # 数据库的列表不能保存None
    chapter_title_list.append( title.string )
    
    if unicode(vol_list[i]).find(u'订阅VIP章节') != -1:
      chapter_title_list[-1] = u'VIP章节'
      break

    li_list = ul_list[i].findAll('li')
    for j in li_list:
      if j.a != None: # 存在空标签，跳过
        url = j.a['href']
        title = unicode(j.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )
        
  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  
  return parse_result
  







#---------------------------------------------------------


def feiku_parse_book(book_url):
  main_url = 'http://www.feiku.com'

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('utf-8', 'ignore')
  document = BSXPathEvaluator(html)
  
  catalog_url_xpath = "//a[@class='bth_12 bth_margin_right']"
  catalog_url = get_xpath_attr(document, catalog_url_xpath, 'href')
  if catalog_url:
    put_into_dict(parse_result, 'catalog_url', catalog_url)
  
  title_xpath = "//div[@class='titile_link']/a[1][@class='rankbold24']"
  put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  
  author_xpath = "//a[@id='aAuthorName']" 
  put_into_dict(parse_result, 'author', get_xpath_string(document, author_xpath))

  update_date_xpath = "//div[@class='main_text']"
  update_date_html = get_xpath_unicode(document, update_date_xpath)
  if update_date_html:
    update_date_re = re.compile(u'\s*(\d*)-(\d*)-(\d*)\s*(\d*):(\d*):(\d*)') 
    update_date = get_re_first(update_date_html, update_date_re)    
    if update_date:
      (year, month, day, hour, minute, second) = update_date
      put_into_dict(parse_result, 'update_date', 
        datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second)) + datetime.timedelta(hours=-8))  
 
  last_url_xpath = "//div[@id='index_body']/div[3][@class='body_view1']/div[1][@class='view5_left']/div[1][@class='main_content']/div[1][@class='main_top']/div[2][@class='main_right']/table[@class='title_txtcolor']/tbody/tr[6]/td/a[@class='graylink']"  
  last_url = get_xpath_attr(document, last_url_xpath, 'href')
  if last_url:
    pos = last_url.rfind('/')
    put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
    put_into_dict(parse_result, 'chapter_url_prefix', main_url + last_url[ : pos+1])

  return parse_result
  

def feiku_parse_chapter(chapter_url):
  main_url = 'http://www.feiku.com'
  main_read_url = chapter_url[ 0 : chapter_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('utf-8', 'ignore')
  document = BSXPathEvaluator(html)

  
  chapter_title_xpath = "//div[@id='chapterContent' and @class='ch']/div[5][@class='chn2']"
  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, chapter_title_xpath))
  

  
  content_xpath = '//div[@id="chcontent"]'
  chapter_content = get_xpath_contents(document, content_xpath)
  if chapter_content:    
    # 开始格式化文本
    paragraph_list = chapter_content.split('<br />')      
    paragraph_list = [x.strip() for x in paragraph_list]
    paragraph_list = [x.replace('&nbsp;&nbsp;&nbsp;&nbsp;',u'　　') for x in paragraph_list if x]
    put_into_dict(parse_result, 'content_list', paragraph_list)
    put_into_dict(parse_result, 'content_type', 'text')

  return parse_result

def feiku_parse_catalog(catalog_url):
  # main_read_url = catalog_url[ 0 : catalog_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)
  
  html = fetch_result.content.decode('utf-8', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}
  
  #title_xpath = '/html/body/center/div/div[2]/div/span'
  #put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))

  vol_list = document.findAll('div', 'title')
  ul_list = document.findAll('table')

  chapter_url_list = []
  chapter_title_list = []
  for i in range(len(vol_list)):
    chapter_url_list.append('') # 数据库的列表不能保存None
    chapter_title_list.append( unicode(vol_list[i].string) )
    
    li_list = ul_list[i].findAll('td')
    for j in li_list:
      if j.a != None: # 存在空标签，跳过
        url = j.a['href']
        url = url[url.rfind('/')+1:]
        title = unicode(j.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )

  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  return parse_result
  
















  
#---------------------------------------------------------


def bingdi_parse_book(book_url):
  main_url = 'http://www.bingdi.com'

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  catalog_url_xpath = '/html/body/div[5]/div/div[6]/div[2]/ul/li/a'
  catalog_url = get_xpath_attr(document, catalog_url_xpath, 'href')
  if catalog_url:
    put_into_dict(parse_result, 'catalog_url', main_url + catalog_url)
   
  title_xpath = '//*[@id="booktitle"]'
  put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  
  author_xpath = '/html/body/div[5]/div/div[3]/div[2]/ul[2]/li[6]/a'
  put_into_dict(parse_result, 'author', get_xpath_string(document, author_xpath))
  
  temp_xpath = '//*[@id="ClbtRight"]'
  temp_html = get_xpath_unicode(document, temp_xpath)
  
  if temp_html:  
    #author_re = re.compile(u'作者：\s*([^;]*)&nbsp') # 名字应该没";"吧
    #put_into_dict(parse_result, 'author', get_re_first(temp_html, author_re))

    update_date_re = re.compile(u'\s*(\d*)-(\d*)-(\d*)\s*(\d*):(\d*):(\d*)') 
    update_date = get_re_first(temp_html, update_date_re)
    if update_date:
      (year, month, day, hour, minute, second) = update_date
      put_into_dict(parse_result, 'update_date', 
        datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second)) + datetime.timedelta(hours=-8))
  
  last_url_xpath = '/html/body/div[5]/div/div[5]/div/a'  
  last_url = get_xpath_attr(document, last_url_xpath, 'href')
  if last_url:
    pos = last_url.rfind('/')
    put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
    put_into_dict(parse_result, 'chapter_url_prefix', main_url + last_url[ : pos+1])    
    
  return parse_result
  

def bingdi_parse_chapter(chapter_url):
  main_url = 'http://www.bingdi.com'
  main_read_url = chapter_url[ 0 : chapter_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
 
  #put_into_dict(parse_result, 'catalog_url', main_read_url + 'List.shtm')
  
  chapter_title_xpath = '/html/body/center/div/div/div[3]/div/span'
  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, chapter_title_xpath))
  

  
  content_xpath = '//*[@id="BookText"]'
  chapter_content = get_xpath_unicode(document, content_xpath)
  if chapter_content:
    if chapter_content.find('id="imgbook"') != -1: # 图片章节
      chapter_content = u'<p>本章为图片</p>'
      img_list = document.findAll('img', id='imgbook')
      for img in img_list:
        img_url = main_url + img['src']
        chapter_content = chapter_content + u'<img src="'+img_url+ '" /><br />'
    else: # 文字章节
      # 开始格式化文本
      chapter_content = chapter_content.replace('&nbsp;&nbsp;&nbsp;&nbsp;',u'　　')
      paragraph_list = chapter_content.split('<br /><br />')
      paragraph_list[0] = paragraph_list[0].replace('<div id="BookText"><br />','')
      paragraph_list[-1] = paragraph_list[-1].replace('</div>','')
      chapter_content = ''.join( ['<p>'+x+'</p>' for x in paragraph_list if x] )
      
    put_into_dict(parse_result, 'content', chapter_content)  

  return parse_result

def bingdi_parse_catalog(catalog_url):
  # main_read_url = catalog_url[ 0 : catalog_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}
  
  #title_xpath = '/html/body/center/div/div[2]/div/span'
  #put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))

  vol_list = document.findAll('div', id='NclassTitle')
  ul_list = document.findAll('ul')

  chapter_url_list = []
  chapter_title_list = []
  for i in range(len(vol_list)):
    title = unicode(vol_list[i].contents[0]).strip('\r\n ')    
    pos = title.find(u'&nbsp;&nbsp;【')     # 去掉多余的部分
    if pos != -1:
      title = title[ 0 : title.find(u'&nbsp;&nbsp;【') ]  
    chapter_url_list.append('') # 数据库的列表不能保存None
    chapter_title_list.append( title )

    li_list = ul_list[i].findAll('li')
    for j in li_list:
      if j.a != None: # 存在空标签，跳过
        url = j.a['href']
        title = unicode(j.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )

  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  return parse_result
  







  
#---------------------------------------------------------


def niepo_parse_book(book_url):
  main_url = 'http://www.niepo.net'

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
   
  #title_xpath = '//*[@id="booktitle"]'
  title_xpath = '//h1'
  put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  #print get_xpath_string(document, title_xpath).encode('utf-8','ignore')
 
  temp_xpath = '/html/body'
  temp_html = get_xpath_unicode(document, temp_xpath)
  
  if temp_html:  
    author_re = re.compile(u'者：\s*([^<]*)</td>') # 名字应该没";"吧
    put_into_dict(parse_result, 'author', get_re_first(temp_html, author_re))    
    update_date_re = re.compile(u'最后更新：(\d*)-(\d*)-(\d*)') 
    update_date = get_re_first(temp_html, update_date_re)   
    if update_date:
      (year, month, day) = update_date
      put_into_dict(parse_result, 'update_date', 
        datetime.datetime(int(year), int(month), int(day)) + datetime.timedelta(hours=-8))
  
  last_url_xpath = "//div[@id='content']/table/tbody/tr[4]/td/table/tbody/tr/td[2]/a[2]"  
  last_url = get_xpath_attr(document, last_url_xpath, 'href')
  if last_url:
    pos = last_url.rfind('/')
    put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
    put_into_dict(parse_result, 'chapter_url_prefix', last_url[ : pos+1])    
  
  return parse_result
  

def niepo_parse_chapter(chapter_url):
  main_url = 'http://www.niepo.net'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
 
  chapter_title_xpath = "//div[@id='title']"
  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, chapter_title_xpath))
  
  content_xpath = "//div[@id='content']"
  chapter_content = get_xpath_contents(document, content_xpath)
  if chapter_content:
    if chapter_content.find('id="imgbook"') != -1: # 图片章节
      chapter_content = u'<p>本章为图片</p>'
      img_list = document.findAll('img', id='imgbook')
      for img in img_list:
        img_url = main_url + img['src']
        chapter_content = chapter_content + u'<img src="'+img_url+ '" /><br />'
      put_into_dict(parse_result, 'content_list', [chapter_content])
      put_into_dict(parse_result, 'content_type', 'image')
        
    else: # 文字章节
      # 开始格式化文本      
      paragraph_list = chapter_content.split('<br />')      
      paragraph_list = [x.strip() for x in paragraph_list]
      paragraph_list = [x.replace('&nbsp;&nbsp;&nbsp;&nbsp;',u'　　') for x in paragraph_list if x]
      put_into_dict(parse_result, 'content_list', paragraph_list)
      put_into_dict(parse_result, 'content_type', 'text')
      


  return parse_result

def niepo_parse_catalog(catalog_url):
  # main_read_url = catalog_url[ 0 : catalog_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}
  
  #title_xpath = '/html/body/div[4]/h1'
  #put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))

  # 本网站有的目录没有分卷
  td_list = document.findAll('td')
  
  chapter_url_list = []
  chapter_title_list = []
  for i in td_list:
    if i.a != None: # 存在空标签，跳过
        url = i.a['href']
        url = url[8 : ]
        title = unicode(i.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )

  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  return parse_result
  









#---------------------------------------------------------


def to92_parse_book(book_url):  

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
   
  title_xpath = "//div[@id='bookTitle']/h1"  
  put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  
  temp_xpath = '/html/body'
  temp_html = get_xpath_unicode(document, temp_xpath)
  
  if temp_html:  
    author_re = re.compile(u'作者：\s*([^&]*)&nbsp;') # 名字应该没"&nbsp;"吧
    put_into_dict(parse_result, 'author', get_re_first(temp_html, author_re))

    update_date_re = re.compile(u'<span id="lbAddTime">\s*(\d*)-(\d*)-(\d*)</span>') 
    update_date = get_re_first(temp_html, update_date_re)
    if update_date:
      (y, m, d) = update_date
      put_into_dict(parse_result, 'update_date', datetime.datetime(int(y), int(m), int(d)) + datetime.timedelta(hours=-8))
  
  last_url_xpath = "//a[@id='hlLastChapter']"  
  last_url = get_xpath_attr(document, last_url_xpath, 'href')
  if last_url:
    pos = last_url.rfind('/')
    put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
    put_into_dict(parse_result, 'chapter_url_prefix', last_url[ : pos+1])
    
  return parse_result
  

def to92_parse_chapter(chapter_url):
  main_read_url = chapter_url[ 0 : chapter_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
 
  #put_into_dict(parse_result, 'catalog_url', main_read_url + 'index.html')
  
  chapter_title_re = re.compile("chaptername\s*=\s*'([^']*)';")
  put_into_dict(parse_result, 'chapter_title', get_re_first(html, chapter_title_re))
  

  
  content_xpath = "//div[@id='content']"
  chapter_content = get_xpath_unicode(document, content_xpath)
  if chapter_content:
    if chapter_content.find('class="imagecontent"') != -1: # 图片章节
      chapter_content = u'<p>本章为图片</p>'
      img_list = document.findAll('img', 'imagecontent')
      for img in img_list:        
        img_url = img['src']
        chapter_content = chapter_content + '<div>'+ '<img src="'+img_url+ '" /></div>'
      put_into_dict(parse_result, 'content_list', [chapter_content])
      put_into_dict(parse_result, 'content_type', 'image')

    else: # 文字章节
      # 开始格式化文本
      paragraph_list = chapter_content.split('<br />')      
      paragraph_list = [x.strip() for x in paragraph_list]
      paragraph_list = [x.replace('&nbsp;&nbsp;&nbsp;&nbsp;',u'　　') for x in paragraph_list if x]
      put_into_dict(parse_result, 'content_list', paragraph_list)
      put_into_dict(parse_result, 'content_type', 'text')    

  return parse_result

def to92_parse_catalog(catalog_url):
  # main_read_url = catalog_url[ 0 : catalog_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}
  
  #title_xpath = '/html/body/div[4]/h1'
  #put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))

  # 本网站有的目录没有分卷
  td_list = document.findAll('td')
  
  chapter_url_list = []
  chapter_title_list = []
  for i in td_list:
    if i.a != None: # 存在空标签，跳过
        url = i.a['href']
        title = unicode(i.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )

  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  return parse_result
  

  
  
  
  
  
  
  
#---------------------------------------------------------


def du101_parse_book(book_url):
  #main_url = 'http://www.101du.net/files/article/info/4/4517.htm'

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
   
  title_xpath = '/html/body/div/div[3]/div[7]/div[3]/div/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr/td/span'
  put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  
  temp_xpath = '/html/body/div/div[3]/div[7]/div[3]/div/table/tbody/tr/td/table'
  temp_html = get_xpath_unicode(document, temp_xpath)
  
  if temp_html:  
    author_re = re.compile(u'者：\s*([^<]*)</td>') # 名字应该没"<"吧
    put_into_dict(parse_result, 'author', get_re_first(temp_html, author_re))

    update_date_re = re.compile(u'更新：\s*(\d*)-(\d*)-(\d*)') 
    update_date = get_re_first(temp_html, update_date_re)
    if update_date:
      (y, m, d) = update_date
      put_into_dict(parse_result, 'update_date', datetime.datetime(int(y), int(m), int(d)) + datetime.timedelta(hours=-8))
  
  last_url_xpath = '/html/body/div/div[3]/div[7]/div[3]/div/table/tbody/tr[4]/td/table/tbody/tr/td[2]/a[2]'  
  last_url = get_xpath_attr(document, last_url_xpath, 'href')
  if last_url:
    pos = last_url.rfind('/')
    put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
    put_into_dict(parse_result, 'chapter_url_prefix', last_url[ : pos+1])
    
  return parse_result
  

def du101_parse_chapter(chapter_url):
  main_read_url = chapter_url[ 0 : chapter_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)

  
  chapter_title_xpath = '//*[@id="title"]'
  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, chapter_title_xpath))
  

  
  content_xpath = '//*[@id="content"]'
  chapter_content = get_xpath_contents(document, content_xpath)
  if chapter_content:
    if chapter_content.find('class="imagecontent"') != -1: # 图片章节
      chapter_content = u'<p>本章为图片</p>'
      img_list = document.findAll('img', 'imagecontent')
      for img in img_list:        
        img_url = img['src']
        chapter_content = chapter_content + '<div>'+ '<img src="'+img_url+ '" /></div>'
      put_into_dict(parse_result, 'content_list', [chapter_content])
      put_into_dict(parse_result, 'content_type', 'image')

    else: # 文字章节
      # 开始格式化文本
      paragraph_list = chapter_content.split('<br />')      
      paragraph_list = [x.strip() for x in paragraph_list]
      paragraph_list = [x.replace('&nbsp;&nbsp;&nbsp;&nbsp;',u'　　') for x in paragraph_list if x]
      put_into_dict(parse_result, 'content_list', paragraph_list)
      put_into_dict(parse_result, 'content_type', 'text')


  return parse_result

def du101_parse_catalog(catalog_url):
  # main_read_url = catalog_url[ 0 : catalog_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}
  
  #title_xpath = '/html/body/div[2]/a[3]/strong'
  #put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))

  # 本网站有的目录没有分卷
  td_list = document.findAll('td')
  
  chapter_url_list = []
  chapter_title_list = []
  for i in td_list:
    if i.a != None: # 存在空标签，跳过
        url = i.a['href']
        title = unicode(i.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )

  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  return parse_result
  






#---------------------------------------------------------


def xs16k_parse_book(book_url):
  main_url = 'http://www.16kxs.com'

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
   
  title_xpath = '/html/body/div[5]/div[2]/div[2]/span'
  title = get_xpath_string(document, title_xpath)
  title_re = re.compile(u'《(.*)》')
  put_into_dict(parse_result, 'title', get_re_first(title, title_re))

  catalog_url_xpath = '/html/body/div[5]/div[2]/div[3]/div[2]/div/ul[6]/a'
  catalog_url = get_xpath_attr(document, catalog_url_xpath, 'href')
  if catalog_url:
    put_into_dict(parse_result, 'catalog_url', main_url + catalog_url)

  author_xpath = '/html/body/div[5]/div[2]/div[3]/div[2]/div/ul[2]/li[6]/a'
  put_into_dict(parse_result, 'author', get_xpath_string(document, author_xpath))
  
  temp_xpath = '/html/body/div[5]/div[2]/div[3]/div[2]/div/ul/li[6]'
  temp_html = get_xpath_unicode(document, temp_xpath)
  
  if temp_html:  
    update_date_re = re.compile(u'\s*(\d*)-(\d*)-(\d*)\s*(\d*):(\d*):(\d*)') 
    update_date = get_re_first(temp_html, update_date_re)
    if update_date:
      (year, month, day, hour, minute, second) = update_date
      put_into_dict(parse_result, 'update_date', 
        datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second)) + datetime.timedelta(hours=-8))  

  last_url_xpath = '/html/body/div[5]/div[2]/div[4]/div[5]/a'  
  last_url = get_xpath_attr(document, last_url_xpath, 'href')
  if last_url:
    pos = last_url.rfind('/')
    put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
    put_into_dict(parse_result, 'chapter_url_prefix', main_url + last_url[ : pos+1])
    
  
    
  return parse_result
  

def xs16k_parse_chapter(chapter_url):
  main_read_url = chapter_url[ 0 : chapter_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)

  
  chapter_title_xpath = '/html/body/center/div/div[2]/div/span'
  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, chapter_title_xpath))
  

  
  content_xpath = '//*[@id="BText"]'
  chapter_content = get_xpath_unicode(document, content_xpath)
  if chapter_content:
    if chapter_content.find('class="imagecontent"') != -1: # 图片章节(本站似乎没有)
      chapter_content = u'<p>本章为图片</p>'
      # img_list = document.findAll('img', 'imagecontent')
      # for img in img_list:        
        # img_url = img['src']
        # chapter_content = chapter_content + '<div>'+ '<img src="'+img_url+ '" /></div>'
    else: # 文字章节
      # 开始格式化文本      
      chapter_content = chapter_content.replace('&nbsp;&nbsp;&nbsp;&nbsp;',u'　　')
      paragraph_list = chapter_content.split('<br /><br />')
      paragraph_list[0] = paragraph_list[0].replace('<div id="BText">','')
      paragraph_list[-1] = paragraph_list[-1].replace('</div>','').rstrip()
      end_pos = paragraph_list[-1].rfind('<font style="display:none">') # 去掉页末的链接  
      if end_pos != -1:
        paragraph_list[-1] = paragraph_list[-1][0:end_pos] 
      
      chapter_content = ''.join( ['<p>'+x+'</p>' for x in paragraph_list if x] )
        
    put_into_dict(parse_result, 'content', chapter_content)  

  return parse_result

def xs16k_parse_catalog(catalog_url):
  # main_read_url = catalog_url[ 0 : catalog_url.rfind('/') + 1] # 后面带'/'
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)
  
  html = fetch_result.content.decode('gbk', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}

  vol_list = document.findAll('div', id='NclassTitle')
  ul_list = document.findAll('ul')

  chapter_url_list = []
  chapter_title_list = []
  for i in range(len(vol_list)):
    title = unicode(vol_list[i].contents[0]).strip('\r\n ')    
    pos = title.find(u'&nbsp;&nbsp;【')     # 去掉多余的部分
    if pos != -1:
      title = title[ 0 : title.find(u'&nbsp;&nbsp;【') ]  
    chapter_url_list.append('') # 数据库的列表不能保存None
    chapter_title_list.append( title )

    li_list = ul_list[i].findAll('li')
    for j in li_list:
      if j.a != None: # 存在空标签，跳过
        url = j.a['href']
        title = unicode(j.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )

  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)  
  return parse_result
 
 
 
# ----------------------------------------------
    
# 纵横，UTF-8   
def zongheng_parse_book(book_url):

  fetch_result = urlfetch.fetch(book_url, allow_truncated=True)
  parse_result = { }
  
  html = fetch_result.content.decode('utf-8', 'ignore')
  document = BSXPathEvaluator(html)
  
  title_xpath = "/html/body/div[2][@class='bodycon']/div[5][@class='wrap']/div[2][@class='mainarea']/div[1][@class='bortable']/div[1][@class='work']/div[1][@class='wright']/h1/a"
  put_into_dict(parse_result, 'title', get_xpath_string(document, title_xpath))
  
  author_xpath = "/html/body/div[2][@class='bodycon']/div[5][@class='wrap']/div[2][@class='mainarea']/div[1][@class='bortable']/div[1][@class='work']/div[1][@class='wright']/h1/em/a"  
  put_into_dict(parse_result, 'author', get_xpath_string(document, author_xpath))

  # 这里可能有两个时间，第一个就是公众更新时间，第二个是VIP时间
  # 我应该获取后一个时间（如果有2个，则获取VIP更新）
  update_date_xpath = '//*[@id="gxzj"]'
  temp_html = get_xpath_unicode(document, update_date_xpath)
  if temp_html:
    update_date_re = re.compile(u'\s*(\d*)-(\d*)-(\d*)\s*(\d*):(\d*):(\d*)') 
    update_date = get_re_last(temp_html, update_date_re)
    if update_date:
      (year, month, day, hour, minute, second) = update_date
      put_into_dict(parse_result, 'update_date', 
        datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second)) + datetime.timedelta(hours=-8))  
 
    # 不过获取的URL还是公众版的
    last_url_re = re.compile('<a href="(http://[^"]*)">')
    last_url =  get_re_first(temp_html, last_url_re)  
    if last_url:
      pos = last_url.rfind('/')
      put_into_dict(parse_result, 'last_url', last_url[ pos+1 : ])
      put_into_dict(parse_result, 'chapter_url_prefix', last_url[ : pos+1])
  
  return parse_result
  

def zongheng_parse_chapter(chapter_url):
  
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  parse_result = { }
  
  html = fetch_result.content.decode('utf-8', 'ignore')
 
  # 转换实体字符  
  document = BSXPathEvaluator(html,convertEntities=BeautifulSoup.HTML_ENTITIES)
  
  chapter_title = document.find(id='readcon').h2
  if chapter_title:
    put_into_dict(parse_result, 'chapter_title', unicode(chapter_title.contents[0]))
  
  content_xpath = '//*[@id="readtext"]'
  paragraph_list = document.getFirstItem(content_xpath).findAll('p')   
  paragraph_list = [unicode(x.contents[0]) for x in paragraph_list]
  
  paragraph_list = [u'　　'+x for x in paragraph_list if x.strip() and x.find('<span')==-1]
  
  put_into_dict(parse_result, 'content_list', paragraph_list)
  put_into_dict(parse_result, 'content_type', 'text')
  return parse_result

def zongheng_parse_catalog(catalog_url):

  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)  

  html = fetch_result.content.decode('utf-8', 'ignore')
  document = BSXPathEvaluator(html)
  
  parse_result = {}

  document = document.find('div', 'chapter')
  
  if not document:
    return
  
  vol_list = document.findAll('h2')
  # 注意VIP有解禁的章节（没有icon）
  ul_list = document.findAll('table')

  chapter_url_list = []
  chapter_title_list = []
  for i in range(len(vol_list)):    
    chapter_url_list.append('') # 数据库的列表不能保存None
    chapter_title_list.append( unicode(vol_list[i].contents[0]) )
    


    li_list = ul_list[i].findAll('td')
    for j in li_list:
      if j.a != None and unicode(j.a).find('[VIP]')==-1: # 跳过VIP章节
        url = j.a['href']
        url = url[url.rfind('/')+1:]
        title = unicode(j.a.string)
        chapter_url_list.append( url ) 
        chapter_title_list.append( title )
        
  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  
  return parse_result
  




    
# 从任何一种类型的网址中，都应该解析出book_url和catalog_url 
# 有的网站从书页网址分析不出内容，则需要在解析书页的时候获取，一般只会出现在书页上
# 注意网址匹配的时候大小写问题
# 目前网址不区分大小写
def get_parse_handle(url):
  info_result = {}
  url = url.lower()
  # 起点中文网
  # http://www.qidian.com/Book/1442549.aspx
  # http://www.qidian.com/BookReader/1442549.aspx
  # http://www.qidian.com/BookReader/1442549,26069303.aspx
  if url.find('qidian') != -1:    
    handle_result = {
      'book': qidian_parse_book,
      'chapter': qidian_parse_chapter,
      'catalog': qidian_parse_catalog,
      }
    info_result['site'] = u'起点'
    if url.find('/book/') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
      info_result['catalog_url'] = url.replace('/book/','/bookreader/')      
    elif url.find(',') != -1:
      info_result['url_type'] = 'chapter'
      info_result['catalog_url'] = url[: url.find(',')] + '.aspx'
      info_result['book_url']  = info_result['catalog_url'].replace('/bookreader/','/book/')
    else:
      info_result['url_type'] = 'catalog'
      info_result['catalog_url'] = url
      info_result['book_url'] = url.replace('/bookreader/','/book/') 
  
  # 飞库
  # http://www.feiku.com/Book/158577/Index.html
  # http://www.feiku.com/html/book/130/158577/List.shtm
  # http://www.feiku.com/html/book/130/158577/4689402.shtm
  elif url.find('feiku') != -1:    
    handle_result = {
      'book': feiku_parse_book,
      'chapter': feiku_parse_chapter,
      'catalog': feiku_parse_catalog,
      }      
    info_result['site'] = u'飞库'
    if url.find('index.html') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
    elif url.find('list.shtm') != -1:
      info_result['url_type'] = 'catalog'
      book_id = re.compile('/(\d*)/list.shtm').findall(url)[0]
      info_result['catalog_url'] = url
      info_result['book_url'] = url[: url.find('/html/book/')] + '/book/' + book_id + '/index.html'
    else:
      info_result['url_type'] = 'chapter' 
      book_id = re.compile('/(\d*)/\d*.shtm').findall(url)[0]
      info_result['catalog_url'] = url[:url.rfind('/')] + '/list.shtm'
      info_result['book_url'] = url[: url.find('/html/book/')] + '/book/' + book_id + '/index.html'
      
  # 冰地
  # http://www.bingdi.com/Article/151479.html
  # http://www.bingdi.com/html/book/130/151479/List.shtm
  # http://www.bingdi.com/html/book/130/151479/4566756.shtm
  elif url.find('bingdi') != -1:
    info_result['site'] = u'冰地'
    handle_result = {
      'book': bingdi_parse_book,
      'chapter': bingdi_parse_chapter,
      'catalog': bingdi_parse_catalog,
      }      
    if url.find('article') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
    elif url.find('list.shtm') != -1:
      info_result['url_type'] = 'catalog'
      book_id = re.compile('/(\d*)/list.shtm').findall(url)[0]
      info_result['catalog_url'] = url
      info_result['book_url'] = url[: url.find('/html/book/')] + '/article/' + book_id + '.html'      
    else:
      info_result['url_type'] = 'chapter'   
      book_id = re.compile('/(\d*)/\d*.shtm').findall(url)[0]
      info_result['catalog_url'] = url[:url.rfind('/')] + '/list.shtm'
      info_result['book_url'] = url[: url.find('/html/book/')] + '/article/' + book_id + '.html'
      
  # 涅破
  # http://www.niepo.net/book/23.html
  # http://www.niepo.net/index/23.html
  # http://www.niepo.net/reader/23-16568.html
  elif url.find('niepo') != -1:
    info_result['site'] = u'涅破'
    handle_result = {
      'book': niepo_parse_book,
      'chapter': niepo_parse_chapter,
      'catalog': niepo_parse_catalog,
      }      
    if url.find('book') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
      info_result['catalog_url'] = url.replace('/book/','/index/')       
    elif url.find('index') != -1:
      info_result['url_type'] = 'catalog'      
      info_result['catalog_url'] = url
      info_result['book_url'] = url.replace('/index/','/book/')       
    else:
      info_result['url_type'] = 'chapter'   
      book_id = re.compile('/(\d*)-').findall(url)[0]
      info_result['catalog_url'] = url[:url.rfind('/reader')] + '/index/' + book_id + '.html'
      info_result['book_url'] = url[:url.rfind('/reader')] + '/book/' + book_id + '.html'
      
      
  # 就爱读书
  # http://www.92to.com/xiaoshuoinfo/67/67346.html
  # http://www.92to.com/files/article/html/67/67346/index.html
  # http://www.92to.com/files/article/html/67/67346/12202834.html
  elif url.find('92to') != -1:
    info_result['site'] = u'就爱'
    handle_result = {
      'book': to92_parse_book,
      'chapter': to92_parse_chapter,
      'catalog': to92_parse_catalog,
      }      
    if url.find('xiaoshuoinfo') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
      temp_url = url.replace('/xiaoshuoinfo/','/files/article/html/')    
      info_result['catalog_url'] = temp_url.replace('.html', '/index.html')
    elif url.find('index.html') != -1:
      info_result['url_type'] = 'catalog'
      info_result['catalog_url'] = url
      temp_url = url.replace('/files/article/html/','/xiaoshuoinfo/')       
      info_result['book_url'] = temp_url.replace('/index.html', '.html')
    else:
      info_result['url_type'] = 'chapter' 
      info_result['catalog_url'] = url[: url.rfind('/')] + '/index.html'
      temp_url = info_result['catalog_url'].replace('/files/article/html/','/xiaoshuoinfo/')
      info_result['book_url'] = temp_url.replace('/index.html', '.html')
      
  # 沸腾文学
  # http://www.101du.net/files/article/info/4/4517.htm
  # http://www.101du.net/files/article/html/4/4517/index.html
  # http://www.101du.net/files/article/html/4/4517/1222090.html
  elif url.find('101du') != -1:
    info_result['site'] = u'沸腾'
    handle_result = {
      'book': du101_parse_book,
      'chapter': du101_parse_chapter,
      'catalog': du101_parse_catalog,
      }      
    if url.find('article/info') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
      temp_url = url.replace('/article/info/','/article/html/')        
      info_result['catalog_url'] = temp_url.replace('.htm', '/index.html')
    elif url.find('index.html') != -1:
      info_result['url_type'] = 'catalog'
      info_result['catalog_url'] = url
      temp_url = url.replace('/article/html/','/article/info/')       
      info_result['book_url'] = temp_url.replace('/index.html', '.htm')
    else:
      info_result['url_type'] = 'chapter' 
      info_result['catalog_url'] = url[: url.rfind('/')] + '/index.html'
      temp_url = info_result['catalog_url'].replace('/article/html/','/article/info/')
      info_result['book_url'] = temp_url.replace('/index.html', '.htm')

  # 16K小说网
  # http://www.16kxs.com/Book/8585/Index.aspx
  # http://www.16kxs.com/Html/Book/8/8585/Index.html
  # http://www.16kxs.com/Html/Book/8/8585/2732589.html
  elif url.find('16kxs') != -1:
    info_result['site'] = u'16K'
    handle_result = {
      'book': xs16k_parse_book,
      'chapter': xs16k_parse_chapter,
      'catalog': xs16k_parse_catalog,
      }      
    if url.find('www.16kxs.com/book/') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
      # catalog_url 需要解析
    elif url.find('index.html') != -1:
      info_result['url_type'] = 'catalog'
      info_result['catalog_url'] = url
      temp_url = url[: url.rfind('/')] # 'http://www.16kxs.com/Html/Book/8/8585'
      temp_url = temp_url[temp_url.rfind('/') : ] # '/8585'  
      info_result['book_url'] = 'http://www.16kxs.com/book' + temp_url + '/index.aspx'
    else:
      info_result['url_type'] = 'chapter' 
      temp_url = url[: url.rfind('/')] # 'http://www.16kxs.com/Html/Book/8/8585'
      info_result['catalog_url'] = temp_url + '/index.html'      
      temp_url = temp_url[temp_url.rfind('/') : ] # '/8585'      
      info_result['book_url'] = 'http://www.16kxs.com/book' + temp_url + '/index.aspx'    
      
  # 纵横中文网
  # http://book.zongheng.com/book/38134.html
  # http://book.zongheng.com/showchapter/38134.html
  # http://book.zongheng.com/chapter/38134/1046576.html
  elif url.find('zongheng') != -1:    
    handle_result = {
      'book': zongheng_parse_book,
      'chapter': zongheng_parse_chapter,
      'catalog': zongheng_parse_catalog,
      }
    info_result['site'] = u'纵横'
    if url.find('/book/') != -1:
      info_result['url_type'] = 'book'
      info_result['book_url'] = url
      info_result['catalog_url'] = url.replace('/book/', '/showchapter/')      
    elif url.find('/showchapter/') != -1:
      info_result['url_type'] = 'catalog'
      info_result['catalog_url'] = url
      info_result['book_url'] = url.replace('/showchapter/','/book/') 
    else:
      info_result['url_type'] = 'chapter'
      temp_url = url[: url.rfind('/')] + '.html'
      info_result['catalog_url'] = temp_url.replace('/chapter/', '/showchapter/') 
      info_result['book_url']  = info_result['catalog_url'].replace('/showchapter/', '/book/')
      
  else:
    return (None, None)

  return (info_result, handle_result)  
    

def get_data(url, url_info = None, url_handle = None):
  if not (url_info and url_handle):
    (url_info, url_handle) = get_parse_handle(url)
  
  if url_info == None:
    return None
  
  book_info = url_info  
  
  # Chapter必须获取 chapter_title，即使它为空 
  if url_info['url_type'] == 'chapter':
    chapter_result = url_handle['chapter'](url)
    if not chapter_result.has_key('chapter_title'):
      chapter_result['chapter_title'] = None
    book_info.update(chapter_result) 

  if url_info['url_type'] == 'book':
    book_result = url_handle['book'](url)    
    if not book_result.has_key('author'):
      book_result['author'] = None
    if not book_result.has_key('title'):
      book_result['title'] = None
    book_info.update(book_result)
    
  if url_info['url_type'] == 'catalog':
    catalog_result = url_handle['catalog'](url)
    book_info.update(catalog_result)
  
  return book_info  
  

  
if __name__== "__main__":
  fetch_result = urllib2.urlopen('http://www.92to.com/files/article/html/67/67346/12202803.html').read()

  #html = fetch_result
  
  #document = BSXPathEvaluator(html, fromEncoding="gbk")
  
  #chapter_title_xpath = '/html/'
  #print get_xpath_string(document, chapter_title_xpath)
  
  print get_parse_handle('http://www.92to.com/files/article/html/67/67346/12202803.html')
  


#--------------------------------- 
# 起点用 re 解析出来的章节列表
#--------------------------------- 
  # list_xpath = '//*[@id="content"]'
  #list_html = unicode(document.getFirstItem(list_xpath))
  
  # book_number = catalog_url[ catalog_url.rfind('/')+1 : catalog_url.rfind('.aspx') ]
  # link_re = re.compile('href=.(' + book_number + ',\d*' + '\.aspx).[^>]*>([^<]*)</a>')
  # list_result = link_re.findall(list_html)

  # if len(list_result) == 0:
    # return None
  
  # main_read_url = 'http://www.qidian.com/BookReader/'
  # catalog_list = []
  # for i in range(len(list_result)):
    # catalog_list.append( {'url': main_read_url + list_result[i][0],
                                 # 'title': list_result[i][1].strip('\r\n ')} )                                 

#--------------------------------- 