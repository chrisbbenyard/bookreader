# -*- coding: utf-8 -*-

from google.appengine.api import urlfetch
from BSXPath import BSXPathEvaluator,XPathResult
from BeautifulSoup import BeautifulSoup

import re
import datetime

from Parser import Parser

def get_xpath_string(document, xpath):
  try:
    return unicode(document.getFirstItem(xpath).contents[0]).strip()
  except:
    return None

def get_xpath_contents(document, xpath):
  try:
    return ''.join( [unicode(x) for x in document.getFirstItem(xpath).contents] ).strip()
  except:
    return None    

## 废弃    
def get_xpath_unicode(document, xpath):
  try:
    return unicode(document.getFirstItem(xpath)).strip()
  except:
    return None
  
def get_xpath_attr(document, xpath, attr):
  try:
    return ((document.getFirstItem(xpath))[attr]).strip()
  except:
    return None
    
def get_re_first(html, r):
  if html:    
    result = re.findall(r, html)
    if len(result) > 0:
      return result[0]  
  return None

# 获取的结构可能比较复杂，所以结果可能需要strip()
def get_item(document, html, xpath_string, re_exp):
 if xpath_string and re_exp:
   return get_re_first( get_xpath_contents(document, xpath_string), re_exp)
 elif xpath_string:
   return get_xpath_contents(document, xpath_string)
 else:
   return get_re_first(html, re_exp)
    
 

# None 和空串不放入字典
# 注意到，如果value是空一类的值，则不要添加到字典
# 因为有可能当前key可以通过别的方式获得，如果赋成了None则会冲掉正确值
# 不过，有的变量必须赋值为None，比如上下章链接，这个在get_data中处理
def put_into_dict(d, key, value):
  if (value != None) and (value != ''):
    d[key] = value
    
# 获取
#   parser    解析器
#   url_info  相关的一些信息
def get_parser(url):    
  
  ## 使用url前部分作为辨识
  key_name_list = [key.name() for key in Parser.all(keys_only=True)]
  
  ##
  url_info = {}
  parser = None
  ##
  for key_name in key_name_list:    
    if url.find(key_name) != -1:    
   
      parser = Parser.get_by_key_name(key_name)    
      ##
      url_info['site'] = parser.site_short_name  
      
      ## url类型
      r_cover = parser.identifier_cover
      r_catalog = parser.identifier_catalog
      r_chapter = parser.identifier_chapter
      url_type = None
      if (r_cover and re.search(r_cover, url)) or (not r_cover and url_type == None):
        url_type = 'cover'
      if (r_catalog and re.search(r_catalog, url)) or (not r_catalog and url_type == None):
        url_type = 'catalog'
      if (r_chapter and re.search(r_chapter, url)) or (not r_chapter and url_type == None):
        url_type = 'chapter'        
      url_info['url_type'] = url_type  
      ## url信息
      if url_type == 'cover':
        url_info['cover_url'] = url    
        if parser.cover2catalog_re:
          url_info['catalog_url']= re.sub(parser.cover2catalog_re, parser.cover2catalog_string, url)             
      elif url_type == 'catalog':
        url_info['catalog_url'] = url
        if parser.catalog2cover_re:
          url_info['cover_url']= re.sub(parser.catalog2cover_re, parser.catalog2cover_string, url)       
      elif url_type == 'chapter':
        url_info['chapter_url'] = url
        if parser.chapter2cover_re:
          url_info['cover_url']= re.sub(parser.chapter2cover_re, parser.chapter2cover_string, url)        
      
  if url_info:  
    return (url_info, parser)
  else:    
    return (None, None)
  
    
def get_data(url):

  (url_info, parser) = get_parser(url)
  
  if url_info == None:
    return None
  
  
  if url_info['url_type'] == 'chapter':    
    result = parse_chapter(url, parser)
    if not result.has_key('chapter_title'):
      result['chapter_title'] = None    
      
  elif url_info['url_type'] == 'cover':
    result = parse_cover(url, parser)
    if not result.has_key('author'):
      result['author'] = None
    if not result.has_key('title'):
      result['title'] = None
   
  elif url_info['url_type'] == 'catalog':  
    result = parse_catalog(url, parser)   

  else:
    pass

  url_info.update(result)  
  return url_info
  
  
def parse_cover(cover_url, parser):

  fetch_result = urlfetch.fetch(cover_url, allow_truncated=True)  
  html = fetch_result.content.decode(parser.site_coding, 'ignore')
  document = BSXPathEvaluator(html, convertEntities=BeautifulSoup.HTML_ENTITIES) # 转换实体字符
  
  parse_result = {}   


  # title
  title = get_item(document, html, parser.title_xpath, parser.title_re)
  put_into_dict( parse_result, 'title', title.strip() )
  # author
  author = get_item(document, html, parser.author_xpath, parser.author_re)
  put_into_dict( parse_result, 'author', author.strip() )

  # update_date  
  update_date = get_re_first(html, parser.update_date_re)
  if update_date and len(update_date)>=3:
    update_date = [int(x) for x in update_date]
    put_into_dict( parse_result, 'update_date', datetime.datetime( *update_date ) + datetime.timedelta( hours=-8 ) )  

    
  last_url = get_xpath_attr(document, parser.last_url_xpath, 'href')
  if last_url:      
    put_into_dict(parse_result, 'last_url', re.sub(parser.last_url_remove_prefix_re, '', last_url ) ) 
    put_into_dict(parse_result, 'chapter_url_prefix', re.sub(parser.chapter_url_prefix_replace_re, parser.chapter_url_prefix_replace_string, last_url ))
  
  return parse_result
  
  
def parse_catalog(catalog_url, parser):
  
  fetch_result = urlfetch.fetch(catalog_url, allow_truncated=True)  
  html = fetch_result.content.decode(parser.site_coding, 'ignore')
  document = BSXPathEvaluator(html, convertEntities=BeautifulSoup.HTML_ENTITIES) # 转换实体字符
  
  parse_result = {} 
  
  vol_list = document.getItemList(parser.vol_and_chapter_xpath)
 
  chapter_url_list = []
  chapter_title_list = []
  
  if parser.url_remove_prefix_re: # 加速，下面要重复使用
    url_remove_prefix_re = re.compile(parser.url_remove_prefix_re)
  
  for i in vol_list:  
    if i.name != 'a':  
      # 判断是否解析到了VIP卷
      if not parser.vol_vip_string or unicode(i).find(parser.vol_vip_string) == -1:      
        chapter_url_list.append('') # 数据库的列表不能保存None    
        chapter_title_list.append( i.contents[0] )    # contents[0]兼容性更强一些
      else:
        chapter_url_list.append('') # 数据库的列表不能保存None    
        chapter_title_list.append( parser.vol_vip_string )   
        break     
    else:            
      url = i['href']
      if parser.url_remove_prefix_re:
        url = url_remove_prefix_re.sub('', url)
      chapter_url_list.append( url ) 
      chapter_title_list.append( unicode(i.contents[0]) )
        
  put_into_dict(parse_result, 'chapter_url_list', chapter_url_list)
  put_into_dict(parse_result, 'chapter_title_list', chapter_title_list)
  
  return parse_result
  
  
  
def parse_chapter(chapter_url, parser):
  fetch_result = urlfetch.fetch(chapter_url, allow_truncated=True)  
  html = fetch_result.content.decode(parser.site_coding, 'ignore')
  document = BSXPathEvaluator(html, convertEntities=BeautifulSoup.HTML_ENTITIES) # 转换实体字符
  
  parse_result = {} 

  put_into_dict(parse_result, 'chapter_title', get_xpath_string(document, parser.chapter_title_xpath))

  if parser.content_link_re:  # 比如起点
    content_link = get_re_first(html, parser.content_link_re) 
    if not content_link:
      return parse_result
    if parser.content_link_prefix:
      content_link = parser.content_link_prefix + content_link
    chapter_content = urlfetch.fetch( content_link, 
                                      allow_truncated=True,
                                      headers = {'Referer': chapter_url}  # 有的网站防止盗链，需要加上这个
                                      ).content.decode(parser.site_coding, 'ignore')
  else:
    chapter_content = get_xpath_contents(document, parser.content_xpath)
  
  # 开始格式化文本

  if parser.content_extract_re:
    chapter_content = get_re_first(chapter_content, parser.content_extract_re) 
 
  if parser.content_split_re:
    paragraph_list = re.split(parser.content_split_re, chapter_content)
  else:
    paragraph_list = [chapter_content]
    
  if parser.content_remove_re:
    remove_re = re.compile(parser.content_remove_re)
    paragraph_list = [remove_re.sub('',x) for x in paragraph_list if x]
    
  paragraph_list = [x.strip() for x in paragraph_list if x.strip()] 

  put_into_dict(parse_result, 'content_list', paragraph_list)
  put_into_dict(parse_result, 'content_type', 'text')
    
  return parse_result
  
if __name__== "__main__":
  pass
## Console debug
# import BookParser
# import Database
# url = 'http://www.qidian.com/Book/1880697.aspx'
# book_info = BookParser.get_data(url)

# book_info.update(BookParser.get_data(book_info['catalog_url']))


# author = book_info['author']
# title = book_info['title']
# catalog_url = book_info['catalog_url']

# book_key_name = Database.generate_book_key_name(author, title)    
# book = Database.Book.get_or_insert(book_key_name)  
    

# catalog_key_name = catalog_url
# catalog = Database.Catalog.get_or_insert(catalog_key_name, book_ref = book)
# catalog.put_info(book_info)

