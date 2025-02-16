import csv
import json
import math
import pandas as pd
import requests
import sys

def getUserId(username):
  url = "https://www.speedrun.com/api/v1/users?name=" + username
  data = requests.get(url).json()['data']
  if len(data) > 0:
    for u in data:
      if u['names']['international'].lower() == username.lower():
        return u['id']
  print(data)
  raise Exception('Searched for ' + username + ', got back ' + str(len(data)) + ' entries (expected 1)') 

def getNextUri(response):
  if 'pagination' in response:
    if 'links' in response['pagination']:
      for x in response['pagination']['links']:
        if x['rel'] == 'next':
          return x['uri']
  return None

def getAllRuns(userid):
  url = "https://www.speedrun.com/api/v1/runs?user=" + userid + "&embed=game,category,region,platform,players"
  df_list = []
  while url != None:
    print(".", end ="")
    response = requests.get(url).json()
    data = response['data']
    df = pd.DataFrame(data)
    if df.shape[0] > 0:
      df['place'] = math.nan
      df.set_index('id', inplace=True)
      df_list.append(df)
    url = getNextUri(response)
  alldf = pd.concat(df_list)
  alldf['place'] = math.nan
  print()
  return alldf

def getPBs(userid, all = False):
  url = "https://www.speedrun.com/api/v1/users/" + userid + "/personal-bests?embed=game,category,region,platform,players"
  data = requests.get(url).json()['data']
  pbdf = pd.DataFrame(data)
  pbdf = pbdf.join(pbdf['run'].apply(pd.Series), rsuffix='run')
  pbdf.set_index('id', inplace=True)
  pbdf.drop(axis=1, columns=['run'], inplace=True)
  df_list = [pbdf]
  if all:
    df = getAllRuns(userid)
    df_list.append(df)
    return pd.concat(df_list)
  return pbdf

def getPlayers(x):
  players = []
  for p in x.players['data']:
    if 'name' in p:
      players.append(p['name'])
    elif 'names' in p:
      players.append(p['names']['international'])
    else:
      print(p)
      raise Exception("Encountered unusual player field.")
  return ", ".join(players)

def getRegion(x):
  if x.region['data'] == []:
    return None
  else:
    return x.region['data']['name']

def getPlatform(x):
  if x.platform['data'] == []:
    return None
  else:
    return x.platform['data']['name']

from time import sleep
varMemo = {}
def getVariable(variableid):
  if variableid not in varMemo:
    url = "https://www.speedrun.com/api/v1/variables/" + variableid
    response = requests.get(url)
    sleep(.1)
    varMemo[variableid] = response.json()['data']
  return varMemo[variableid]

def getValue(variableid, valueid):
  var = getVariable(variableid)
  return var['values']['values'][valueid]['label']

def getVariables(x, subcats):
  if x['values'] == {}:
    return None
  else:
    variables = []
    for varid, valid in x['values'].items():
      if getVariable(varid)['is-subcategory'] == subcats:
        variables.append(getValue(varid, valid))  
      retval = " -- ".join(variables)
    return retval

def getVideo(x):
  vids = [y['uri'] for y in x['links']]
  return " | ".join(vids)
    
if len(sys.argv) != 3:
  print(sys.argv[0] + ": export your SRC PBs to a csv file")
  print()
  print("Usage: python " + sys.argv[0] + " <SRC user name> <output csv filename>" )
  exit(-1)

username = sys.argv[1]
outfilename = sys.argv[2]
print('Retrieving runs for', username)
userid = getUserId(username)
rawdf = getPBs(userid, all=True)

print('Processing data...')
runsdf = pd.DataFrame()
runsdf['place'] = rawdf['place']
runsdf['game'] = rawdf.apply(lambda x: x.game['data']['names']['international'], axis=1)
runsdf['category'] = rawdf.apply(lambda x: x.category['data']['name'], axis=1)
runsdf['subcategory(s)'] = rawdf.apply(lambda x: getVariables(x, True), axis=1)
runsdf['variable(s)'] = rawdf.apply(lambda x: getVariables(x, False), axis=1)
runsdf['platformname'] = rawdf.apply(lambda x: getPlatform(x), axis=1)
runsdf['regionname'] = rawdf.apply(lambda x: getRegion(x), axis=1)
runsdf['players'] = rawdf.apply(lambda x: getPlayers(x), axis=1)
runsdf['time'] = rawdf.apply(lambda x: x['times']['primary_t'], axis=1)
runsdf['date'] = rawdf.apply(lambda x: x['date'], axis=1)
runsdf['video'] = rawdf.apply(lambda x: getVideo(x['videos']), axis=1)
runsdf['comment'] = rawdf.apply(lambda x: str(x['comment']).replace('\n', ' ').replace('\r', ' ') , axis=1)

runsdf.drop_duplicates(subset=['game','category','subcategory(s)','variable(s)','platformname','regionname','players','time','date','video','comment'], keep="first", inplace=True)

runsdf.to_csv(outfilename, index=False, quoting=csv.QUOTE_NONNUMERIC)
print(username, "PBs exported to", outfilename)
