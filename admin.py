# -*- coding: utf-8 -*-

import os
import urllib 
import re
import xml.etree.ElementTree as etree

# 使用新的版本的django
# from google.appengine.dist import use_library
# use_library('django', '1.1')

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache

import Database
from Parser import Parser


def get_broken_bookmarks():
  all_bookmarks_query = Database.Bookmark.all() 
  broken_bookmarks = []
  for bookmark in all_bookmarks_query:
    try:
      bookmark.user_ref
      bookmark.book_ref
      bookmark.catalog_ref
    except:
      broken_bookmarks.append(bookmark)
      
  return broken_bookmarks
  
def get_broken_chapters():
  last_chapter_cursor = memcache.get('chapter_cursor')
  checked_chapter_number = memcache.get('checked_chapter_number')
  if not checked_chapter_number:
    checked_chapter_number = 0
  broken_chapters = memcache.get('broken_chapters')
  if not broken_chapters:
    broken_chapters = []
    
  return (broken_chapters, checked_chapter_number, last_chapter_cursor)


 
def get_broken_catalogs():
  all_catalogs_query = Database.Catalog.all()
  broken_catalogs = []
  for catalog in all_catalogs_query:
    try:
      catalog.book_ref
    except:
      broken_catalogs.append(catalog)
  
  return broken_catalogs
  
def get_all_lastcheck_keys():
  return [key for key in Database.LastCheck.all(keys_only=True)]   

def get_all_chapter_keys():
  return [key for key in Database.Chapter.all(keys_only=True)]   
  
def export_parser():
  return '<parser>\n' + ''.join([x.to_xml().encode('utf-8') for x in Parser.Parser.all() ]) + '</parser>'
  
def import_parser(xml_string):
  tree = etree.fromstring(xml_string.encode('utf-8'))
  tree = etree.ElementTree(tree)
  entity_list = tree.findall('entity')
  for entity in entity_list:
    # # # # # l = tree.findall('property')
    # # # # # r = tree.getroot()  
    # # # # # print l[9].attrib 
    # # # # # exec 'k.title_xpath="1"'

    
  
class AdminPage(webapp.RequestHandler):
  def get(self):
    user_email = users.get_current_user().email()
    
    (broken_chapters, checked_chapter_number, last_chapter_cursor) = get_broken_chapters()
    
    template_values = {
      'logout_url': users.create_logout_url(self.request.uri), 
      'nickname': user_email,
      'broken_bookmarks_number': len(get_broken_bookmarks()),
      'broken_catalogs_number': len(get_broken_catalogs()),
      'lastcheck_keys_number': len(get_all_lastcheck_keys()),
      
      'checked_chapter_number': checked_chapter_number,
      'last_chapter_cursor': last_chapter_cursor,      
      'broken_chapters_number': len(broken_chapters),     
      }

    path = os.path.join(os.path.dirname(__file__), 'template/admin.html')
    self.response.out.write(template.render(path, template_values))
    
    
class TaskCheckBrokenChapters(webapp.RequestHandler):
  def post(self):
    all_chapters_query = Database.Chapter.all()  
    
    (broken_chapters, checked_chapter_number, last_chapter_cursor) = get_broken_chapters()  
    
    if last_chapter_cursor:    
      all_chapters_query.with_cursor(last_chapter_cursor)
    else:
      checked_chapter_number = 0
      broken_chapters = []
        
    chapters = all_chapters_query.fetch(20)        
    for chapter in chapters:
      checked_chapter_number = checked_chapter_number + 1
      try:
        chapter.catalog_ref
      except:
        broken_chapters.append(chapter.key())
    
    if chapters:
      last_chapter_cursor = all_chapters_query.cursor()
    else:
      last_chapter_cursor = None
      
    memcache.set('chapter_cursor', last_chapter_cursor)
    memcache.set('broken_chapters', broken_chapters)
    memcache.set('checked_chapter_number', checked_chapter_number)

    if last_chapter_cursor:
      taskqueue.add(url='/admin/task/check_broken_chapters', params={})
  
  def get(self):
    taskqueue.add(url='/admin/task/check_broken_chapters', params={})
    self.redirect('/admin')
    
  
class DeleteAllLastCheck(webapp.RequestHandler):
  def get(self):
    lastcheck_keys = get_all_lastcheck_keys()
    Database.db.delete(lastcheck_keys)
    self.redirect('/admin')
    
class DeleteAllChapters(webapp.RequestHandler):
  def get(self):
    chapter_keys = get_all_chapter_keys()
    while chapter_keys:        
        Database.db.delete(chapter_keys[0:500]) 
        chapter_keys = chapter_keys[500:]
    self.redirect('/admin')
    
class DeleteBrokenBookmarks(webapp.RequestHandler):
  def get(self):
    broken_bookmarks = get_broken_bookmarks()   
    Database.db.delete(broken_bookmarks)     
    self.redirect('/admin')
    
class DeleteBrokenCatalogs(webapp.RequestHandler):
  def get(self):
    broken_catalogs = get_broken_catalogs()  

    for catalog in broken_catalogs:
      catalog.delete_with_chapters_and_bookmarks()
     
    self.redirect('/admin')
    
class DeleteBrokenChapters(webapp.RequestHandler):
  def get(self):
    (broken_chapters, checked_chapter_number, last_chapter_cursor) = get_broken_chapters()   
    Database.db.delete(broken_chapters)     
    # 重新检查
    taskqueue.add(url='/admin/task/check_broken_chapters', params={})
    self.redirect('/admin')

class UserManage(webapp.RequestHandler):
  def get(self):
    all_users_query = Database.User.all()
    all_users = []
    for user in all_users_query:
      all_users.append({
        'username': user.key().name()[4:],
        'bookmark_number': len(user.get_user_bookmark_keys()),
        'delete_link': '/admin/user/delete/' + str(user.key()),
        })
    
    template_values = {
      'all_users': all_users,
      }

    path = os.path.join(os.path.dirname(__file__), 'template/admin_users.html')
    self.response.out.write(template.render(path, template_values))    
  

class DeleteUser(webapp.RequestHandler):
  def get(self, key_str):
    user = Database.User.get( Database.db.Key(encoded = key_str) )
    if user:
      user.delete_with_bookmarks()
    else:
      self.response.out.write('The user does not exists!')
    
    self.redirect('/admin/users')
    
    
    
class BookManage(webapp.RequestHandler):
  def get(self):
    all_books_query = Database.Book.all()
    all_books = []
    
    for book in all_books_query:
      book_info = book.get_info()
      book_info['catalogs'] = []
      book_info['delete_link'] = '/admin/book/delete/' + str(book.key())
      for catalog in book.catalogs: 
        catalog_info = catalog.get_info()  
        catalog_info['chapter_number'] = catalog.get_chapter_number()
        catalog_info['user_list'] = catalog.get_user_nicknames()
        catalog_info['user_number'] = len(catalog_info['user_list'])
        catalog_info['user_list'] = ', '.join(catalog_info['user_list'])
        catalog_info['delete_link'] = '/admin/catalog/delete/' + str(catalog.key())
        book_info['catalogs'].append(catalog_info)
      all_books.append(book_info)
      
    template_values = {
      'booklist': all_books,
      }

    path = os.path.join(os.path.dirname(__file__), 'template/admin_books.html')
    self.response.out.write(template.render(path, template_values))   
  


class DeleteBook(webapp.RequestHandler):
  def get(self, key_str):
    book = Database.Book.get( Database.db.Key(encoded = key_str) )
    if book:
      for catalog in book.catalogs:
        catalog.delete_with_chapters_and_bookmarks()
      book.delete()
    else:
      self.response.out.write('The catalog does not exists!')
    
    self.redirect('/admin/books')

class DeleteCatalog(webapp.RequestHandler):
  def get(self, key_str):
    catalog = Database.Catalog.get( Database.db.Key(encoded = key_str) )
    if catalog:
      catalog.delete_with_chapters_and_bookmarks()
    else:
      self.response.out.write('The catalog does not exists!')
    
    self.redirect('/admin/books')
    
class ManageParser(webapp.RequestHandler):
  def get(self):

    template_values = {
      
      }

    path = os.path.join(os.path.dirname(__file__), 'template/admin_parser.html')
    self.response.out.write(template.render(path, template_values))   


class ExportParser(webapp.RequestHandler):
  def get(self):
    xml_content = export_parser()
         
    if not xml_content:
      self.response.out.write('Empty!')
      return
    
    # 设置header
    self.response.headers['Content-Type'] = 'application/octet-stream;charset=utf-8' 
    self.response.headers['Content-Disposition'] = 'attachment;filename="parser.xml"'

    self.response.out.write(xml_content)    


    
class ImportParser(webapp.RequestHandler):
 

  def post(self):    
    self.response.out.write("hello")   

    

        


    
application = webapp.WSGIApplication(
                                     [('/admin', AdminPage),
                                     
                                      ('/admin/task/check_broken_chapters', TaskCheckBrokenChapters),
                                      
                                      ('/admin/delete_broken_bookmarks', DeleteBrokenBookmarks),
                                      ('/admin/delete_broken_catalogs', DeleteBrokenCatalogs),
                                      ('/admin/delete_broken_chapters', DeleteBrokenChapters), 
                                      ('/admin/delete_all_lastcheck', DeleteAllLastCheck), 
                                      ('/admin/delete_all_chapters', DeleteAllChapters),
                                      
                                      ('/admin/users', UserManage),
                                      ('/admin/user/delete/(.*)', DeleteUser),
                                      ('/admin/books', BookManage),
                                      ('/admin/book/delete/(.*)', DeleteBook),
                                      ('/admin/catalog/delete/(.*)', DeleteCatalog),
                                      
                                      ('/admin/parser', ManageParser),
                                      ('/admin/parser/export', ExportParser),
                                      ('/admin/parser/import', ImportParser),
                                     ],
                                     debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()