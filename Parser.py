﻿# -*- coding: utf-8 -*-

#-----------------
# 保存解析数据的数据库
# 
# 
# 
#-----------------


from google.appengine.ext import db


# 解析网站所需的信息
# key_name = [url] 
class Parser(db.Model):    
  ## 常规项目
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
  last_url_replace_re = db.TextProperty()                 # 重整last_url
  last_url_replace_string = db.TextProperty()             # ..
  chapter_url_prefix_replace_re = db.TextProperty()       # 章节url前缀
  chapter_url_prefix_replace_string = db.TextProperty()   # ..
  
  
  ## 目录  
  vol_and_chapter_list_re = db.TextProperty()       # 卷和章节
  vol_vip_string = db.TextProperty()                # VIP卷，解析到此为止
  url_remove_prefix_re = db.TextProperty()          # 章节url处理
  url_remove_prefix_string = db.TextProperty()      # ..
  
  ## 章节
  chapter_title_xpath = db.TextProperty()   # 章节的标题
  content_link_xpath = db.TextProperty()    # 内容链接解析(该死的起点)
  content_xpath = db.TextProperty()         # 内容解析
  content_format_re = db.TextProperty()     # 格式化文本
  content_format_string = db.TextProperty() # ..
  content_split_string = db.TextProperty()  # 文本分段
  
    