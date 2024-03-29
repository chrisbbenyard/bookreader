﻿# -*- coding: utf-8 -*-

#-----------------
# 保存解析数据的数据库
# 
# 
# 
#-----------------


from google.appengine.ext import db
import xml.etree.ElementTree as etree


# 解析网站所需的信息
# key_name = [identifier] 
# 注意不要数字开头，比如92to就不行，使用http://www.92to.com代替 
class Parser(db.Model):    
  ## 常规项目
  site_url = db.TextProperty()            # 网站地址
  site_coding = db.TextProperty()         # 网站编码
  site_name = db.TextProperty()           # 网站名称
  site_short_name = db.TextProperty()     # 网站简略名称，用于显示，通常为2个汉字
  site_description = db.TextProperty()    # 网站描述
  
  ## 识别串
  identifier_cover = db.TextProperty()    # 封面识别串
  identifier_catalog = db.TextProperty()  # 目录识别串
  identifier_chapter = db.TextProperty()  # 章节识别串
  
  ## url转换
  catalog2cover_re = db.TextProperty()      # Catalog to Cover
  catalog2cover_string = db.TextProperty()  # ..
  chapter2cover_re = db.TextProperty()      # Chapter to Cover
  chapter2cover_string = db.TextProperty()  # ..
  cover2catalog_re = db.TextProperty()      # Cover to Catalog
  cover2catalog_string = db.TextProperty()  # ..

  
  ## 封面
  title_xpath = db.TextProperty()         # 标题
  title_re = db.TextProperty()            # ..
  author_xpath = db.TextProperty()        # 作者
  author_re = db.TextProperty()           # ..
  update_date_xpath = db.TextProperty     # 更新时间
  update_date_re = db.TextProperty()      # ..
  
  last_url_xpath = db.TextProperty()      # 最后更新章节
  last_url_remove_prefix_re = db.TextProperty()           # 重整last_url
  chapter_url_prefix_replace_re = db.TextProperty()       # 章节url前缀
  chapter_url_prefix_replace_string = db.TextProperty()   # ..
  
  
  ## 目录  
  vol_and_chapter_xpath = db.TextProperty()       # 卷和章节
  vol_vip_string = db.TextProperty()              # VIP卷，解析到此为止
  url_remove_prefix_re = db.TextProperty()        # 章节url处理

  
  ## 章节
  chapter_title_xpath = db.TextProperty()     # 章节的标题

  content_link_code = db.TextProperty()       # 计算实际链接，使用字符串形式的代码，get_content_link
  content_xpath = db.TextProperty()           # 内容解析
  
  content_extract_re = db.TextProperty()      # 进一步提取内容（提取出段落部分）
  
  image_link_code = db.TextProperty()         # 单独为图片解析，因为有的网站没有图片，有的网站图片在内容中，有的网站图片也是计算链接，get_image_link
    
  content_split_re = db.TextProperty()        # 文本分段
  content_remove_re = db.TextProperty()       # 移除
  

def export_parser():
  return '<parser>\n' + ''.join([x.to_xml().encode('utf-8') for x in Parser.all() ]) + '</parser>'
  
def import_parser(xml_string):
  tree = etree.fromstring(xml_string)
  tree = etree.ElementTree(tree)  
  for entity  in tree.findall('entity'):    
    key = entity.attrib.get('key')
    if key:
      key_name = db.Key(encoded=key).name()
    else:
      key_name = entity.attrib.get('key_name')
    # 如果没有办法获取key_name
    if not key_name:
      continue
    parser = Parser.get_or_insert(key_name)
    for property in entity.findall('property'):
      property_name = '_' + property.attrib['name']
      property_type = property.attrib['type']
      if property_type != 'null':      
        property_value = property.text
        if property_type == 'text' and property_value == None:
          property_value = ''
        vars(parser)[property_name] = property_value
    
    parser.put()
    
def get_parser_info():  
  parser_info = []
  for parser in Parser.all():
    parser_info.append({
      'site_name': parser.site_name,
      'site_url': parser.site_url,              
      })
  return parser_info
    