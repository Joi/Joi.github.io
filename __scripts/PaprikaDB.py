#!/usr/bin/env python3
# Paprika Database
# This script connects to Paprika app's SQLite database and pull out whatever we want and format it as JSON, YAML, whatever.

# NOTES:
# Before running the first time: 1. create a file in the same directory as this Notebook, named "config.py" 2. copy paste this line:
# path_project = "/local/path/to/this/repo/joi.github.io"
# (which should be the path to the direcotry one level up from where this file here is.)

# pip3 install mistletoe
# pip install Unidecode | https://pypi.org/project/Unidecode/
# pip install pathvalidate | https://pypi.org/project/pathvalidate/
# pip install pyyaml
# pip install python-frontmatter
# pip install titlecase - 2021-04-11

# REGARDING MARKDOWN
# We ran with Commonmakr for a while but ran into an issue: it doesn't do tables.
# A quick fix was to switch to "Markdown-It" https://github.com/executablebooks/markdown-it-py


print("\n\n\n---------------------------------------\nEXECUTING PaprikaDB EXPORT\n---------------------------------------\n")

# IMPORTS -------------------------------------
# speedracergogogo
import time
start_time = time.time()

import os
import re
import shutil
import datetime
from datetime import datetime
from operator import itemgetter
import zipfile
import json
import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
#from mdit_py_plugins.front_matter import front_matter_plugin
import frontmatter
import pprint
from pathvalidate import sanitize_filename
import unidecode
import sqlite3
from sqlite3 import Error
from pathlib import Path
from shutil import copyfile
from collections import defaultdict
from titlecase import titlecase
import config # This imports our local config file, "config.py". Access vars like so: config.var


# INITIALIZE CLASSES ------------------------------
# Markdown-It
mdit = (
    MarkdownIt()
    .use(footnote_plugin)
    #.use(front_matter_plugin)
    #.disable('image')
    .enable('table')
)

# VARS -----------------------------------------

# Debug?
debug = False

# Date time stamp
now = datetime.now()
# DT stamp restricted to the hour. For the local database backups.
dt_hourly = now.strftime("%Y-%m-%d %H.00")
#print(dt_hourly)

# Environment-dependent Paths
path_project    = config.path_project # manually set in config.py, which is NOT checked into GIT.
path_user_home  = str(Path.home())    # automatically detects the User home directory path from the OS/ENV

# Paprika Database Path
filename_db     = 'Paprika.sqlite'
path_paprika    = '/Library/Group Containers/72KVKW69K8.com.hindsightlabs.paprika.mac.v3/Data/'
path_db_sub     = path_paprika + 'Database/'
path_db_med     = path_user_home + path_db_sub
path_db_full    = path_user_home + path_db_sub + filename_db
path_photos     = path_user_home + path_paprika + 'Photos/'

# Paprika Databse Backup. / We create this before we do anything, just in case.
file_db_bu          = 'Paprika-BU-' + dt_hourly + '.sqlite'
path_db_bu_sub      = path_project + '/__scripts/backups/'
path_db_bu          = path_db_bu_sub + file_db_bu + '.zip'

# Replaces Above "Working"
path_temp_working   = path_db_bu_sub + "tmp/" # put tmp in backup
path_db_working     = path_temp_working + filename_db

# Output
path_json_data       = path_project + '/_data/'
path_recp_mkdn_files = path_project + '/_recipes/'
path_meal_mkdn_files = path_project + '/_notes/'
path_tags_mkdn_files = path_project + '/_tags/'
path_pags_mkdn_files = path_project + '/_pages/'
path_post_mkdn_files = path_project + '/_posts/'
path_recp_phot_files = path_project + '/images/recipes/'

# Paths to dirs of markdown data/content which Jekyll knows about but this script doesn't yet
paths_jekyll_mkdn_dirs = [
  path_meal_mkdn_files,
  path_pags_mkdn_files,
  path_post_mkdn_files
  ]

# Paparika Timestamp Offset: 978307200
ts_offset = 978307200


# Tag Case edge cases
tag_special_cases = {
  'bbq': 'BBQ',
  'jnat': 'Jnat',
  'kio': 'Kio',
  'wagyu': 'Wagyu',
  'chinese': 'Chinese',
  'french': 'French',
  'indian': 'Indian',
  'indonesian': 'indonesian',
  'italian': 'Italian',
  'japanese': 'Japanese',
  'mexican': 'Mexican',
  'middle east': 'Middle East',
  'thai': 'Thai',
  'vietnamese': 'Vietnamese',
}
# The above rendered as a list:
tag_special_cases_list = []
for tel,teu in tag_special_cases.items():
  tag_special_cases_list.append(teu)

print ("✅ IMPORTs completed and VARs initiated\n")

# - FUNCTIONS ----------------------------------

# Utility Functions ----------------------------

# Clobber a string into a filename -------------
def make_filename(string):
    string = unidecode.unidecode(string)
    string = string.replace(" &","") # Need to strip out amperstands. See content.html liquid too.
    string = string.replace(" ","-")
    invalid = r'.<>:"/\|?* ,()“”‘’\''
    for char in invalid:
        string = string.replace(char, '')
    string = sanitize_filename(string).lower().rstrip('-').replace('---','-')
    string = string.lower()
    return string

# Delete and Create Output Directories
def pheonix_output_directories(path):
  if os.path.exists(path):                  # If path exists,
    shutil.rmtree(path, ignore_errors=True) # burn it down.
  os.mkdir(path)                            # Then raise it anew

# Turn a multiline text block into a Markdown List
def make_markdown_list(text):
    return "* " + text.replace("\n", "\n* ") 


# Database Functions ---------------------------

# Connect to Database
def db_connect(db_file):
    try:
        conn = sqlite3.connect(db_file)
        # row_factory does some magic for us
        # see: https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
        # https://docs.python.org/3/library/sqlite3.html#accessing-columns-by-name-instead-of-by-index
        conn.row_factory = sqlite3.Row
    except Error as e:
        print(e)
    return conn

def db_query_magic(db_cursor):
  # For the next bit with columns and results and dict and zip, see:
  # https://stackoverflow.com/questions/16519385/output-pyodbc-cursor-results-as-python-dictionary/16523148#16523148
  #
  # This grabs the key (cur.description) for us
  columns = [column[0] for column in db_cursor.description]
  rows = db_cursor.fetchall()
  results = []
  for row in rows:
      results.append(dict(zip(columns, row))) # glue the key to the value
  return results


# Parse Paprika Markdown-ish into Markdown
    # if 0 == recipe -> pass 1 to make_filename()
    # if 0 == photo -> take 1 as key into {photos_dict} and get filename
def paprika_markdownish(content,photos_dict):
    if content:
        content = re.sub(r'\[(photo):(.+?)\]',lambda x: '![' + x.group(2) + '](/images/recipes/' + photos_dict[x.group(2)] + ')',content)
        #content = re.sub(r'\[(recipe):(.+?)\]',lambda x: '[' + x.group(2) + '](/recipes/' + make_filename(x.group(2)).lower() + ')',content)
        # This is for if we want ObsidianMD instead of regular
        content = re.sub(r'\[(recipe):(.+?)\]',lambda x: '[[' + make_filename(x.group(2)) + '|' + x.group(2) + ']]',content)
        return content
    else:
        raise ValueError("content null")

# Simple naïve wrapper around opening, writing to and closing a file.
def write_file(path,content):
    f = open(path, 'w')
    f.write(str(content))
    f.close()

def write_json_file(data,path):
  write_file(path,json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1))


def parse_tag_string(tag_str):
  # In cases where Tags have been entered on a signle line 
  #   with a single white space &/or comman between them:
  # Test string (put in tags as one line on a Page)
  #   "test1,test2, test3 test4"
  space = " "
  comma = ","
  if comma in tag_str:
    tag_str = tag_str.replace(","," ")
  if space + space in tag_str:
    tag_str = tag_str.replace("  "," ")
  if space in tag_str:
    tag_str = tag_str.split(" ")
  else:
    tag_str = [tag_str]
  return tag_str

# Check if tag is an exception
# If so, return that
# If not, return untouched
# and If titlecasing (non-exceptions), do that
def display_tag(tag,mode = None):
  try:
    tag = tag_special_cases[tag]# + " EDGECASE"
  except:
    if mode == "titlecase":
      tag = titlecase(tag)# + " Titled"
    else:
      tag = tag# + " untouched"
  return tag

# Given a List
# Return an alphabetically grouped and sorted List of lists
def make_alpha_grouped_list(the_list, pops=None):
  list_alpha_grouped={}
  for list_items in the_list:
      list_alpha_grouped.setdefault(list_items[0].lower(),[]).append(list_items)
  if pops:
    for pop in pops:
      list_alpha_grouped.pop(pop)
  for k,v in list_alpha_grouped.items():
    list_alpha_grouped[k] = sorted(v)
  sorted(list_alpha_grouped)
  return list_alpha_grouped


print ("✅ FUNCTIONS defined\n")


# OUTPUT DESTINATION DIRECTORIES ---------------------

# If these Output Paths don't exist, create them
if not os.path.exists(path_db_bu_sub):
    os.mkdir(path_db_bu_sub)

# These ones we want to recreate every time ----------
# Recipe Markdown Stubs Directory
pheonix_output_directories(path_recp_mkdn_files)
# Tag Markdown Stubs Directory
pheonix_output_directories(path_tags_mkdn_files)
# Recipe Renamed Photos Directory
pheonix_output_directories(path_recp_phot_files)

print ("✅ DIRECTORIES created\n")


# DATABASE BACKUPS -----------------------------------

# Make a zipped backup of the DB
zipfile.ZipFile(path_db_bu, mode='w').write(path_db_full, arcname=file_db_bu, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


# Make a temp copy of the DB to work with. We delete it later.
#
# First, check if the temp folder already exists and if so delete it
if os.path.exists(path_temp_working):
    shutil.rmtree(path_temp_working, ignore_errors=True) #nuke the temp working dir.
# create a var here just to capture the useless out put of the copyfile() function
shutil.copytree(path_db_med, path_temp_working) # and copy it over

print ("✅ DATABASE Backed up\n")



# DATABASE OPERATIONS ------------------------------

# First Database Operation: WAL Checkpoint
# This writes the log and flushes the cache
conn = db_connect(path_db_working)
cur = conn.cursor()
cur.execute("PRAGMA wal_checkpoint;")
conn.close()

# Second Database Operation: Get our recipe Data
conn = db_connect(path_db_working)
with conn:
    cur = conn.cursor()
    cur.execute(f"""
      SELECT 
        GROUP_CONCAT(C.ZNAME,"|") as `categories`,
        R.ZCOOKTIME         as `cook_time`,
        R.ZINTRASH          as `intrash`,
        datetime(R.ZCREATED + {ts_offset},'unixepoch')
                            as `created`,
        R.ZCREATED + {ts_offset}
                            as `created_ts`,
        R.ZDESCRIPTIONTEXT  as `description`,
        R.ZDIFFICULTY       as `difficulty`,
        R.ZDIRECTIONS       as `directions`,
        R.ZINGREDIENTS      as `ingredients`,
        R.ZIMAGEURL         as `image_url`,
        R.ZNAME             as `name`,
        R.ZNOTES            as `notes`,
        R.ZNUTRITIONALINFO  as `nutritional_info`,
        R.ZONFAVORITES      as `favorite`,
        R.ZPHOTO            as `photo_thumb`,
        R.ZPHOTOLARGE       as `photo_large`,
        R.ZPREPTIME         as `prep_time`,
        R.ZRATING           as `rating`,
        R.ZSERVINGS         as `servings`,
        R.ZSOURCE           as `source`,
        R.ZSOURCEURL        as `source_url`,
        R.ZTOTALTIME        as `total_time`,
        R.ZUID              as `uid`,
        R.Z_PK              as `p_recipe_id`,
        -- We need to do these SELECTS because
        -- otherwise the Category concat
        -- replicates itself the number of times
        -- there are images. No idea why.
        (
          SELECT
            GROUP_CONCAT(RP.ZFILENAME,"|") as filename
          FROM
            ZRECIPEPHOTO as RP
          WHERE
            RP.ZRECIPE = R.Z_PK
        ) as photos_filenames,
        (
          SELECT
            GROUP_CONCAT(RP.ZNAME,"|") as name
          FROM
            ZRECIPEPHOTO as RP
          WHERE
            RP.ZRECIPE = R.Z_PK
        ) as photos_names,
        (
          SELECT
            GROUP_CONCAT(date(M.ZDATE + {ts_offset},'unixepoch'),"|") as dates
          FROM
            ZMEAL AS M
          WHERE
            M.ZRECIPE = R.Z_PK
        ) as meal_dates,
        (
          SELECT
            GROUP_CONCAT(M.ZTYPE,"|") as types
          FROM
            ZMEAL AS M
          WHERE
            M.ZRECIPE = R.Z_PK
        ) as meal_types

      FROM
        ZRECIPE as R

      LEFT JOIN  Z_12CATEGORIES AS RC
        ON  RC.Z_12RECIPES = R.Z_PK
      LEFT JOIN  ZRECIPECATEGORY AS C
        ON  RC.Z_13CATEGORIES = C.Z_PK

      WHERE
        R.ZINTRASH IS 0

      GROUP BY  R.Z_PK;
      """
    )
#  AND ( R.ZRATING = 5 OR C.ZNAME LIKE '%mine%')

results = db_query_magic(cur)

print ("✅ DATABASE Queried For Recipes\n")

# CLOSE DB ------------------------------------------------------------------------
conn.close()
print ("✅ DATABASE Closed\n")


# --------------------------------------------------------------------------------------
# Create dicts to hold 
cats    = defaultdict(dict) # the cats -> recipes dictionary
tags    = defaultdict(dict) # the tags -> docs dictionary


# --------------------------------------------------------------------------------------
# Loop through Results
for result in results:
    result['photos_dict'] = {}
    result['html'] = {}
    result['type'] = None
    result['mine'] = None

    # RECIPE_FILENAME : 
    # This is also our Key between the YAML in Markdown stubs and the JSON Data files
    recipe_filename = make_filename(result['name'])
    result['slug'] = recipe_filename
    result['permalink'] = '/recipes/'+recipe_filename


    # --------------------------------------------------------------------------------------
    # Start of RESULT Items FOR loop {


    # ---------------------------------------------------
    # Photos Stuff
    # We do this first so we have access to the photo data when parsing Paprika Markdown-ish [photo:name]
    # Split concatened photo filenames and names into a lists
    try:
        result['photos_filenames'] = result['photos_filenames'].split('|')
    except:
        pass
    try:
        result['photos_names'] = result['photos_names'].split('|')
        # if we have photo_names, zip filenames & names into into a key=value dict
        # We will use this for the PMD parse below
        result['photos_dict'] = dict(zip(result['photos_names'], result['photos_filenames']))
    except:
        result['photos_dict'] = None
        pass

    # ----------------------------------------------------------------
    # Some notes about photos ----------------------------------------
    # Paprika has several types of photos it manages in different ways:
    # 1. The Recipe Thumbnail
    #     a) This is either generated from the source recipe, 
    #        or set from the first photo uploaded to the recipe
    #     b) its UID is stored in the Recipe table, in the PHOTO column.
    # 2. The Recipe "large photo"
    #     a) Same provenance as Thumbnail, just the larger version of it.
    # 3. User-uploaded photos
    #     a) photos the user uploads into Paprika themselves are assigned UIDs 
    #        and numbered names (editable in the recipe edit view).
    #     b) all their metadata is stored in its own table ('ZRECIPEPHOTO') 
    #        and related via the recipe ID (not UID)
    #
    #  We need to copy both kinds with new file names over. 
    #  The thumbs will simply be named "thumb"
    #
    # ----------------------------------------------------------------

    # Disabled. I generated this and printed out a JSON file to use as a guide. Not needed in production, 
    # but as we ain't done yet, keeping it around.
    #photos[result['uid']] = {'recipe_filename':recipe_filename,'recipe_thumb':result['photo_thumb'], 'recipe_photos':result['photos_dict']}

    # We need to move and rename the photo files and vars (which go into the recipe stubs), here, all at once. 
    result['photos_filenames_new'] = []
    result['photos_dict_new'] = {}

    # First, if this recipe result has any photos
    if result['photo_thumb'] or result['photos_dict']:
      source_path_recipe_photos = path_photos + result['uid'] + "/"
      dest_path_recipe_photos = path_recp_phot_files + "/"

      if result['photo_thumb']:
        try:
          # New photo_thumb file name
          new_photo_thumb = recipe_filename + "-thumb.jpg"
          #copy the thumbnail over
          shutil.copy2(source_path_recipe_photos + "/" + result['photo_thumb'], dest_path_recipe_photos + new_photo_thumb)
          result['photo_thumb'] = new_photo_thumb
          if debug:
            print("\t- Thumb: " + recipe_filename + "")
        except:
          print( "🛑 THUMBNAIL PHOTO Missing for " + recipe_filename )

      if result['photo_large']:
        try:
          # New photo_large file name
          new_photo_large = recipe_filename + "-large.jpg"
          #copy the large photo over
          shutil.copy2(source_path_recipe_photos + "/" + result['photo_large'], dest_path_recipe_photos + new_photo_large)
          result['photo_large'] = new_photo_large
          if debug:
            print("\t- Large: " + recipe_filename + "")
        except:
          print( "🛑 LARGE PHOTO Missing for " + recipe_filename )

      if result['photos_dict']:
        #print("\n" + recipe_filename + ": has photos_dict")
        for photo_name,pd2 in result['photos_dict'].items():
          photo_name_fn = make_filename(photo_name)
          #print("\tphoto name:" + photo_name + "\n\tphoto UID:" + pd2)
          try:
            new_photo_filename = recipe_filename + "-" + photo_name_fn + ".jpg"
            shutil.copy2(source_path_recipe_photos + "/" + pd2,dest_path_recipe_photos + new_photo_filename)
            result['photos_filenames_new'].append(new_photo_filename)
            result['photos_dict_new'][photo_name] = new_photo_filename
            if debug:
              print("\t- Moved: " + new_photo_filename + "")

          except Exception as e:
            print( "🛑 MISSING PHOTOS for " + recipe_filename + ": " + new_photo_filename )
            #print(e)
            print("-------")
        
        result['photos_dict'] = result['photos_dict_new']



    # ---------------------------------------------------
    # Meal Dates
    # Split concatened mealdates into a list
    rmeal_dates = ""
    if result['meal_dates']:
      try:
        result['meal_dates'] = result['meal_dates'].split('|')
        for meal_date in result['meal_dates']:
          rmeal_dates += "- [[" + meal_date + "|recipenote]]\n"
        rmeal_dates  = mdit.render(rmeal_dates)
        #if debug:
            #print("\t- MD'ed Meal Dates: " + rmeal_dates + "")
        
      except Exception as e:
          print( "🛑 Something fubar in rmeal_dates: " + rmeal_dates + "\n")
          print(e)
          print("-------\n")



    # ---------------------------------------------------
    # Directions, Descriptions, Ingredients, Nutritional Info
    if result['directions']:
      rdirections  = paprika_markdownish(result['directions'],result['photos_dict'])
      rdirections  = mdit.render(rdirections)
    else:
      rdirections = None

    if result['description']:
      rdescription = paprika_markdownish(result['description'],result['photos_dict'])
      rdescription = mdit.render(rdescription)
    else:
      rdescription = None

    if result['ingredients']:
      list_ing_lines   = paprika_markdownish(result['ingredients'],result['photos_dict'])
      list_ing_lines   = re.sub('\\\\x{0D}','\n',list_ing_lines)
      list_ing_lines   = re.sub('\n\n','\n',list_ing_lines)
      list_ing_lines   = make_markdown_list(list_ing_lines)
      ringredients = mdit.render(list_ing_lines)
    else:
      ringredients = None

    if result['nutritional_info']:
      rnutrition = mdit.render(str(result['nutritional_info']))
    else:
      rnutrition = None

    if result['notes']:
      result['notes'] = paprika_markdownish(result['notes'],result['photos_dict'])
      rnotes = mdit.render(result['notes'])
    else:
      rnotes = None

    result['html'] = {
      'directions'  : rdirections,
      'description' : rdescription,
      'ingredients' : ringredients,
      'nutrition'   : rnutrition,
      'notes'       : rnotes,
      'meal_dates' : rmeal_dates
      }

    # ---------------------------------------------------
    # Categories
    # Split concatened categories into a list
    if result['categories']:
      remove_cats_hacks = ['_mine','_stub']
      try:
        result['categories'] = result['categories'].lower().split('|') # Forcing Cats to lowercase
        for cl in result['categories']:
          
          # Using the categories as a toggle hack ("recipe by Joi or not", etc…)
          if cl == "_mine":
            result['mine'] = 1
          if cl == "_stub":
            result['type'] = 'stub'

          if cl not in cats.keys():
            cats[cl] = {}
          
          # Here we create the Tags array and insert the Recipe data.
          # This will only contain tags that are used as Categories in Paprika Recipes.
          # We still need to go and iterate over all the Markdown files and extract the tags from them.
          # Any tags that are not already created by recipes will need to be then, and etc…
          if cl not in tags.keys():
            #tags[cl] = {'recipes':[],'notes':{'feature':[],'rough':[]},'pages':[]}
            tags[cl] = {'recipes':[],'rel_tags':[]}
          append_to_recipes = {'title':result['name'],'permalink':result['permalink'],'photo_thumb':result['photo_thumb'], 'mine':result['mine'], 'rating':result['rating']}
          tags[cl]['recipes'].append(append_to_recipes)
          # hawt lambda sorting magik https://www.geeksforgeeks.org/ways-sort-list-dictionaries-values-python-using-lambda-function/
          #tags[cl]['recipes'] = sorted(tags[cl]['recipes'], key = lambda i: i['title'])
          # Same, using itemgetter (more efficient) https://www.geeksforgeeks.org/ways-sort-list-dictionaries-values-python-using-itemgetter/
          # requires `from operator import itemgetter` though
          tags[cl]['recipes'] = sorted(tags[cl]['recipes'], key=itemgetter('title'))

          if recipe_filename not in cats[cl].keys():
            cats[cl][recipe_filename] = str(result['name'])

          # Add the "categories", modulo the current one and the hacks, to the relative_tags list
          remove_for_rel = remove_cats_hacks + [cl]
          tags[cl]['rel_tags'] += [i for i in result['categories'] if i not in remove_for_rel]


      except Exception as e:
        print( "🛑 Something fubar in categories for " + recipe_filename + "\n")
        print(e)
        print("-------\n")
      result['categories'] = [i for i in result['categories'] if i not in remove_cats_hacks]
      result['tags'] = result['categories']
    result.pop('categories')

    # ---------------------------------------------------
    # Sources
    if result["source"] == "":
      result["source"] = None 
    if result["source_url"] == "":
      result["source_url"] = None 

    # Clean out a bit of stuff
    result.pop('photos_dict_new')
    result.pop('photos_filenames')
    result.pop('photos_filenames_new')
    result.pop('photos_names')

    # end of RESULT Items FOR loop }
    # --------------------------------------------------------------------------------------

    
    # Going to split the "result" array into bits we want in the YAML and stuff we will put
    # in the content body
    result2 = result
    content = {}
    content["html"] = result2['html']
    del result2['html'], result2['directions'], result2['notes'], result2['nutritional_info']
    # We keep "result2['ingredients']" because content.html needs it for link previews.

    output2  = "---\n"
    output2 += "title: \"" + result2['name'] + "\"\n"
    output2 += "filename: \"" + recipe_filename + "\"\n"
    # Dumping all recipe metadata as YAML here
    output2 += yaml.dump(result2)
    output2 += "---\n"

    # We open Row One and include  _includes/backlinks.html in the _layouts/recipe.html tempplate.
    output2 += '<div class="large-8 medium-7 columns" id="writeup">'
    if result2['mine']:
      if content['html']['description']:
        output2 += '\t\t<div id="description"><h4>Description</h4>\n<div class="box box-description content">'+ content['html']['description'] + '</div></div>'
    if content['html']['notes']:
      output2 += '\t\t<div id="notes"><h4>Notes</h4>\n<div class="box box-notes">' + content['html']['notes'] + '</div></div>'
    output2 += '\t</div><!-- #writeup -->\n'
    output2 += '</div><!-- #row-one -->\n'

    output2 += '<div class="row" id="row-two">'
    output2 += '\t<div class="medium-4 small-5 columns" id="ingredients">'
    if content['html']['ingredients']:
        output2 += '<h4>Ingredients</h4><div class="box box-ingredients content">' + content['html']['ingredients'] + '</div>'
    output2 += '\t</div>'
    output2 += '\t<div class="medium-6 small-7 columns" id="directions">'
    if result2['mine']:
      if content['html']['directions']:
        output2 += '<h4>Directions</h4><div class="box box-directions content">' + content['html']['directions'] + '</div>'
    output2 += '\t</div>'


    # Create/Open a text file for each recipe and write the above Markdown string into it
    mdFilePath = path_recp_mkdn_files + recipe_filename + ".md"
    write_file(mdFilePath,output2)

    del result,result2,output2,content

print ("✅ RECIPE RESULTS Looped and Acted upon\n")
# END RECIPES ---------------------------------------------------------------------




# START MEALS ---------------------------------------------------------------------

# Second Database Operation: Get our recipe Data
conn = db_connect(path_db_working)
with conn:
    cur2 = conn.cursor()
    cur2.execute(f"""
      SELECT 
        M.ZRECIPE as recipe_id,
        M.ZNAME as recipe_name,
        M.ZDATE + {ts_offset} as `meal_date_ts`,
        DATE(M.ZDATE, 'unixepoch', '+31 year', 'localtime') as `meal_date`,
        M.ZTYPE as meal_type_code,
        MT.ZNAME as meal_type_name

      FROM
        ZMEAL as M

      LEFT JOIN ZMEALTYPE AS MT
        ON MT.Z_PK = M.ZTYPE

      WHERE
      M.ZRECIPE is not NULL

      GROUP BY
        M.Z_PK
      ORDER BY
        meal_date_ts ASC
      ;
      """
    )

data_meals = db_query_magic(cur2)

print ("✅ DATABASE Queried For Meals\n")

# CLOSE DB ------------------------------------------------------------------------
conn.close()
print ("✅ DATABASE Closed\n")


# Initialise MEALS Indices dict
meals_indices = defaultdict(dict)
# RECIPE by DATE and MEAL
meals_indices['recipe_by_date_and_meal'] = defaultdict(dict)
# MEAL by RECIPE and DATE
meals_indices['meal_by_recipe_and_date'] = defaultdict(dict)
# MEAL GROUPED NOTES & DATA by RECIPE and DATE
meals_indices['meal_data_by_recipe_and_status'] = defaultdict(dict)
# MEAL by DATE and RECIPE
meals_indices['meal_by_date_and_recipe'] = defaultdict(dict)

write_json_file(data_meals,path_json_data + "debug.json")

# Loop the data into the new struct
for data_meal in data_meals:
  meal_date             = data_meal['meal_date']
  meal_recipe_id        = data_meal['recipe_id']
  meal_recipe_name      = data_meal['recipe_name']
  meal_recipe_filename  = make_filename(data_meal['recipe_name'])
  meal_type_name        = data_meal['meal_type_name']



  # RECIPE by DATE and MEAL ---
  # If the `meal_type_name` key doesn't exist, we need to initialise the list
  try:
    meals_indices['recipe_by_date_and_meal'][meal_date][meal_type_name]
  except:
    meals_indices['recipe_by_date_and_meal'][meal_date][meal_type_name] = []
  
  # Creating both here and can decide later which one to use.
  # Create the meal dict with name and filename
  append_meal_dict = {
    'recipe_id'       : meal_recipe_id,
    'recipe_filename' : meal_recipe_filename,
    'recipe_name'     : meal_recipe_name
  }
  # Create the meal id list (we'll need to do lookup in recipe YAML data)
  append_meal_list = meal_recipe_id



  # and append it to the existing date dict, which is "defaultdicts" initialised before the FOR
  meals_indices['recipe_by_date_and_meal'][meal_date][meal_type_name].append(append_meal_list)

  # MEAL by RECIPE and DATE ---
  meals_indices['meal_by_recipe_and_date'][meal_recipe_id][meal_date] = meal_type_name

  # MEAL by DATE and RECIPE ---
  meals_indices['meal_by_date_and_recipe'][meal_date][meal_recipe_id] = meal_type_name



  # MEAL GROUPED NOTES & DATA by RECIPE and DATE ---

  note_file = path_meal_mkdn_files + meal_date + "-" + meal_type_name + ".md"
  append_nofile_regular = {'date': meal_date, 'type': meal_type_name}

  if os.path.isfile(note_file):
    parsed_note = frontmatter.load(note_file)
    try:
      append_featured = {'date': meal_date, 'type': meal_type_name, 'feature': parsed_note['feature']}
      try:
        meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['featured']
      except:
        meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['featured'] = []
      meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['featured'].append(append_featured)
    except:
      try:
        meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['regular']
      except:
        meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['regular'] = []
      meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['regular'].append(append_nofile_regular)
  else:
    try:
      meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['nofile']
    except:
      meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['nofile'] = []
    meals_indices['meal_data_by_recipe_and_status'][meal_recipe_id]['nofile'].append(append_nofile_regular)


print ("✅ MEAL RESULTS Looped and Acted upon\n")


# Peek into the Markdown files ------------------------------------------

# Get the _Notes dir's files' tags lists & add to tags[]
for meal_mkdn_file in sorted(os.listdir(path_meal_mkdn_files)):

  meal_mkdf_filename_pat = "^(\d\d\d\d)-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])-(\w+).md$"
  meal_mkdf_filename_mat = re.match(meal_mkdf_filename_pat, meal_mkdn_file)
  #if meal_mkdn_file != ".DS_Store":
  if meal_mkdf_filename_mat:

    # We get the date and meal type out of the filename regex match check above.
    meal_year = meal_mkdf_filename_mat.group(1)
    meal_mnth = meal_mkdf_filename_mat.group(2)
    meal_day  = meal_mkdf_filename_mat.group(3)
    meal_type = meal_mkdf_filename_mat.group(4)
    meal_date = meal_year + "-" + meal_mnth + "-" + meal_day 
    meal_mkdn_file_path = path_meal_mkdn_files + meal_mkdn_file
    # ! ! ! Weak link: Replicating the Note Permalink from Jekyll's _config.yml 
    meal_uri_path = "/notes/"+ meal_year +"-"+ meal_mnth +"-"+ meal_day +"-" + meal_type + ".html"

    # Now, we need to open each file …
    if os.path.isfile(meal_mkdn_file_path):
      parsed_note = frontmatter.load(meal_mkdn_file_path) # See note "Parsed Note" at foot
      # and pull out the value of "feature" key.
      feature = parsed_note.get('feature')
      # If there is one, it is a "featured" meal note,
      if (feature):
        note_type = "feature"
        append_to_note = {'date':meal_date,'type':meal_type,'feature':feature,'uri_path':meal_uri_path}
      # If there isn't, it's a "rough" meal note
      else:
        note_type = "rough"
        append_to_note = {'date':meal_date,'type':meal_type,'uri_path':meal_uri_path}

      parsed_note_tags = parsed_note.get('tags')
      if parsed_note_tags != None:
        if type(parsed_note_tags) is str:
          parsed_note_tags = parse_tag_string(parsed_note_tags)
        if type(parsed_note_tags) is list:
          parsed_note_tags = [x.lower() for x in parsed_note_tags]
          for tag in parsed_note_tags:
            try:
              tags[tag]['notes']
            except:
              tags[tag]['notes'] = {'feature':[],'rough':[]}
            tags[tag]['notes'][note_type].append(append_to_note)
            try:
              tags[tag]['rel_tags']
            except:
              tags[tag]['rel_tags'] = []
            # add the note tags, modulo the current tag
            tags[tag]['rel_tags'] += [i for i in parsed_note_tags if i not in [tag]]
            #print(tag + ": " + json.dumps(tags[tag], indent=1) + "\n")


# Get the _Pages dir's files' tags lists & add to tags[]
for page_mkdn_file in sorted(os.listdir(path_pags_mkdn_files)):

  page_mkdf_filename_pat = "^(.*).md$"
  page_mkdf_filename_mat = re.match(page_mkdf_filename_pat, page_mkdn_file)

  if page_mkdf_filename_mat:
    page_mkdn_file_path = path_pags_mkdn_files + page_mkdn_file

    if os.path.isfile(page_mkdn_file_path):
      parsed_page = frontmatter.load(page_mkdn_file_path) # See note "Parsed Note" at foot
      parsed_page_tags = parsed_page.get('tags')
      parsed_page_title = parsed_page.get('title')
      # Process Tags
      if parsed_page_tags != None:
        if type(parsed_page_tags) is str:
          parsed_page_tags = parse_tag_string(parsed_page_tags)
        if type(parsed_page_tags) is list:
          parsed_page_tags = [x.lower() for x in parsed_page_tags]
          for tag in parsed_page_tags:
            try:
              tags[tag]['pages']
            except:
              tags[tag]['pages'] = []
            tags[tag]['pages'].append(parsed_page_title)
            try:
              tags[tag]['rel_tags']
            except:
              tags[tag]['rel_tags'] = []
            # add the page tags, modulo the current tag
            tags[tag]['rel_tags'] += [i for i in parsed_page_tags if i not in [tag]]
            #print(tag + ": " + json.dumps(tags[tag], indent=1) + "\n")

      # Process Titles
      if parsed_page_title != None:
        try:
          pages
        except:
          pages = []
        # add the title to the list
        #pages += [parsed_page_title] # both these methods work :)
        pages.append(parsed_page_title)


# Alphabetically Grouped and Sorted Tags with title case and filename slugs
# Really inefficient…
# must be a better way to do this with comprehension or lambda/map…
tags_alpha_grouped = make_alpha_grouped_list(tags,['_'])
#print(json.dumps(tags_alpha_grouped,indent=1))

tags_alpha_grouped_2 = {}
for letter,tagos in tags_alpha_grouped.items():
  tags_alpha_grouped_2[letter] = {display_tag(tago):{'titlecase':display_tag(tago,'titlecase'),'filename':make_filename(tago)} for (tago) in tagos}
tags_alpha_grouped = tags_alpha_grouped_2
del tags_alpha_grouped_2

# Alphabetically Grouped and Sorted Pages
pages_alpha_grouped = make_alpha_grouped_list(pages)
#print(json.dumps(pages_alpha_grouped,indent=1))

# File writing and Miscellaneous cleanup ------------------------------------------

# Tag Page Markodwn Stubs
# Loop to generate:
# 1. Consolidated Tag counts
# 2. Tag Page Markdown Slugs
for tag, tagd in tags.items():
  # Take the list of accumulated tags and generate a count+filenamed dict for each unique tag
  tagd['rel_tags_count'] = {make_filename(raw_tag_label) : [tagd['rel_tags'].count(raw_tag_label),display_tag(raw_tag_label)]
    for raw_tag_label in set(tagd['rel_tags'])}
  tagd.pop('rel_tags') # discard the list
  # Make those slugs
  tag_filename = make_filename(tag)
  tag_title = display_tag(tag,'titlecase')
  try:
    te = tag_special_cases[tag_filename]
    tag_key = te
    #print(tag_key + "YES edgecase")
  except:
    tag_key = tag_filename
    #print(tag_key + "NO edgecase")
  tag_yaml = yaml.dump(tagd)
  tag_content = "---\ntitle: " + tag_title + "\ntag_key: " + tag_key + "\n" + tag_yaml + "\n---\n"
  write_file(path_tags_mkdn_files + tag_filename + ".md",tag_content)


# Convert the data structs to JSON and dump to individual files

# Tag Edge Cases Data Dump
write_json_file(tag_special_cases,path_json_data + "tag_special_cases.json")
print ("✅ TAG EDGECASES JSON Indices Dumped\n")

# Tag Indices Data Dump
write_json_file(tags,path_json_data + "tags.json")
write_json_file(tags_alpha_grouped,path_json_data + "tags_alpha_grouped.json")
print ("✅ TAGS JSON Indices Dumped\n")

# Category Indices
write_json_file(cats,path_json_data + "recipe_categories.json")
print ("✅ CATEGORY JSON Indices Dumped\n")

# Meals Indices
write_json_file(meals_indices,path_json_data + "meals_indices.json")
print ("✅ MEALS JSON Indices Dumped\n")

# Pages Indices Data Dump
write_json_file(pages_alpha_grouped,path_json_data + "pages_alpha_grouped.json")
print ("✅ TAGS JSON Indices Dumped\n")


# CLEANUP --------------------------------------------
# Delete the temp working direcotry
shutil.rmtree(path_temp_working, ignore_errors=True) # "ignore errors" nukes it
print ("\n✅ CLEANUP Complete\n")

exectime = round((time.time() - start_time),3)
print("------------------------------\n⏱  %s seconds \n------------------------------\n" % exectime)
print ("😎🤙🏼 We're done here.\n")

"""
NOTES ----------------------------------

"Parsed Notes"
There's a missed opportunity here, to be leveraged later, to add the contents of the 
Markdown files to the script's"knowledge". 
This would require building an overall "memory", perhaps Object?

"""