#Get the streaming API and get mention and retweet
import os

#Spotify Connection Authorization
import sys
import urllib

#Importing Twitter
import numpy as np
import sys
import time
from TwitterAPI import TwitterAPI

global limit

followers_dict = {} #limit of number of tweets



# Authorize Twitter
def get_twitter():
    """ Construct an instance of TwitterAPI using the tokens you entered above.
    Returns:
      An instance of TwitterAPI.
    """
    #twitter authorization
    consumer_key = 'rUloSGBGvaS4FGKqVWMRZOfly'
    consumer_secret = 'gshJohkZqPnMk2StyBPEnU03ZzyYuhaTwReGp2YAkoqKUH9JfK'
    access_token = '428180671-oyVOMEOw77UYpTRCaHs4LZxd8o3PlAiYe0OPNaU5'
    access_token_secret = 'UNNQWBVFPFw5OEm2ChKbMkBqYXwWOx3yxWuFrLsJKIBhn'
    return TwitterAPI(consumer_key, consumer_secret, access_token, access_token_secret)

#avoid the rate limit of twitter by using robust_request
def robust_request(twitter, resource, params, max_tries=5):
    """ If a Twitter request fails, sleep for 15 minutes.
    Do this at most max_tries times before quitting.
    Args:
      twitter .... A TwitterAPI object.
      resource ... A resource string to request; e.g., "friends/ids"
      params ..... A parameter dict for the request, e.g., to specify
                   parameters like screen_name or count.
      max_tries .. The maximum number of tries to attempt.
    Returns:
      A TwitterResponse object, or None if failed.
    """
    for i in range(max_tries):
        request = twitter.request(resource, params)
        if request.status_code == 200:
            return request
        else:
            print('Got error %s \nsleeping for 15 minutes.' % request.text)
            sys.stderr.flush()
            time.sleep(61 * 15)


def get_user_info(twitter,screen_name):
    """
    Get the user twitter id and screen name based on id
    Args:
        twitter: twitter object
        screen_name: screen name of the users
    Return:
        tuple of screen_name with the corresponding user id
    """
    req = robust_request(twitter,'users/lookup',
                        {'screen_name':screen_name}).json()[0]
    print("got info for %s" %req['screen_name'])
    return (req['id'],req['screen_name'])

def get_user_tweets(twitter,user_id,count,include_rt):
    """
    Get the user's tweets, right now it's excluding retweets and replies
    Args:
        twitter: twitter object
        user_id: id of the user want to use
        count: number of tweets we want to get
    Return:
        tuple of screen_name with the corresponding user id
    """
    tweets = []
    if not include_rt:
        start = time.time()
        max_id = 0
        req = robust_request(twitter,'statuses/user_timeline',
                            {'user_id':user_id,
                            'language':'en','exclude_replies':'true','include_rts':'false','count':200}).json()
        if len(req) == 0:
            print("got nothing from this user")
            return None
        else:
            total_count = 0
            for r in req:
                total_count = r['user']['statuses_count']
                if max_id == 0:
                    max_id = r['id']
                elif r['id'] < max_id:
                    max_id = r['id']
                tweets.append((r['id'],r['text']))

            #if user tweet less than 200 => return immediately
            if total_count <= 200:
                return tweets

            #if not and not getting enough tweets, loop to start getting more
            while len(tweets)<count:
                if time.time()-start >= 60:
                    print("time out,can't get more tweets from this user,")
                    return tweets
                max_id -= 1
                req = robust_request(twitter,'statuses/user_timeline',
                            {'user_id':user_id,
                            'language':'en','exclude_replies':'true','include_rts':'false','count':200,'max_id':max_id}).json()
                for r in req:
                    if max_id == 0:
                        max_id = r['id']
                    elif r['id'] < max_id:
                        max_id = r['id']
                    tweets.append((r['id'],r['text']))
            return tweets[:count]
    else:
        req = robust_request(twitter,'statuses/user_timeline',
                            {'user_id':user_id,
                            'language':'en','count':200}).json()
        if len(req) == 0:
            print("got nothing from this user")
            return None
        else:
            for r in req:
                tweets.append((r['id'],r['text']))
            return tweets

def get_retweet_users(twitter,tweet_id):

    #Change the count for number of retweet id
    """
    Get the user that retweet a specific tweet
    Args:
        twitter: twitter object
        tweet_id: id of the tweet
    Return:
        list of users that retweet the specified tweet.Each user is a
        tuple of screen name and id
    """
    s = 'statuses/retweets/:' + str(tweet_id)
    req = robust_request(twitter,s,
                {'id':tweet_id,
                'count':2,'trim_user':'false'}).json()
    users = [(r['user']['id'],r['user']['screen_name']) for r in req]
    return users


def create_users_dict_from_rt(twitter,exemplar,tweet):
    global followers_dict
    rt_users = get_retweet_users(twitter,tweet[0])
    print("Got rt_users ",rt_users[0])
    for user in rt_users:
        if user[0] not in followers_dict:
            followers_dict[user[0]] = {}
            rt_user_tweets = get_user_tweets(twitter,user[0],5,True)
            if rt_user_tweets:
                user_final = {}
                user_final['id'] = user[0]
                user_final["screen_name"]=user[1]
                user_final["tweets"]=rt_user_tweets
                user_final["rt_from_tweet"] = tweet
                user_final["exemplar"] = exemplar
                user["friends"] = get_friends(twitter,user[0])

                #Keying by user id
                followers_dict[user[0]] = user_final


def combine_retweet_users(twitter,exemplar,count):
    """
    Combine all functions to get users who retweet the exemplar's older tweets
    Args:
        twitter: twitter object
        followers_dict: global dict of all the users we want to search for.
        exemplar: exemplar user object retrieved from get_user_info

    Return:
    """
    global followers_dict
    tweets = get_user_tweets(twitter,exemplar[0],count,False)
    print("Get tweets ",tweets[0])
    for tweet in tweets:
        create_users_dict_from_rt(twitter,exemplar,tweet)
    print("finish retweet users")

def get_friends(twitter,user_id):
    req = robust_request(twitter,'friends/ids',
            {'user_id':user_id,'count':5000}).json()
    return req['ids']


def mention_list_extraction(twitter,user,count,exemplar,hashtag):
    """
    user:   0: user id
            1: user name
            2: tweet id
            3: tweet text
            4: exemplar
    """
    global followers_dict

    if user[0] not in followers_dict:
        user_tweets = get_user_tweets(twitter,user[0],count,True)
        if user_tweets:
            user_final = {}
            user_final['id'] = user[0]
            user_final["screen_name"]=user[1]
            user_final["tweets"]=user_tweets
            user_final["mention_in_tweet"]=user[3]
            user_final["exemplar"] = exemplar
            user_final["friends"] = get_friends(twitter,user[0])
            user_final["hashtag"] = hashtag

            #Keying by user id
            followers_dict[user[0]] = user_final

def combine_mention_users(twitter,exemplar,count):
    print("got to mention for ",exemplar[1])
    req = robust_request(twitter,'search/tweets',
                {'q':exemplar[1],'count':100}).json()
    for t in req['statuses']:
        mention = "@"+exemplar[1]
        not_mention = "RT @"+exemplar[1]
        hashtag ="#"+exemplar[1]
        if mention in t['text'] and not_mention not in t['text']:
            print("MENTION ",t['text'])
            mention_list_extraction(twitter,(t['user']['id']
                                    ,t['user']['screen_name'],t['id'],t['text']),5,exemplar,False)
        if hashtag in t['text']:
            print("HASHTAG ",t['text'])
            mention_list_extraction(twitter,(t['user']['id']
                                ,t['user']['screen_name'],t['id'],t['text']),5,exemplar,True)

if __name__ == '__main__':
    """
    followers_dict: global dict of all the users we want to search for.
        Each user is a dict with keys:
            screen_name: user info
            tweets: their most recent tweets
            mention_in_tweet: the tweet that mention the exemplar
            rt_from_tweets: the tweet the user retweeted from
            exemplar: the exemplar the user refered to

    """
    twitter = get_twitter()

    #Get retweets
    exemplar = get_user_info(twitter,"Nike")
    combine_retweet_users(twitter,exemplar,1)
    print("Finish retweet users")
    #Get mentions
    combine_mention_users(twitter,exemplar,1)
    #Start getting to the streaming part
    print("Start getting to the stream")
    req = robust_request(twitter,'statuses/filter',
                    {'track':exemplar[1],
                    'language':'en',
                    'follow':exemplar[0]})
    mention_list = []
    mention ="@"+exemplar[1]
    not_mention = "RT @"+exemplar[1]
    hashtag ="#"+exemplar[1]
    for t in req:
        #if the tweet is from exemplar => check retweet:
        if t['user']['id'] == exemplar[0]:
            create_users_dict_from_rt(twitter,(t['id'],t['text']))

        #If the tweet mention:
        if mention in t['text'] and not_mention not in t['text']:
            print("MENTION ",t['text'])
            mention_list_extraction(twitter,(t['user']['id']
                                    ,t['user']['screen_name'],t['id'],t['text']),5,exemplar,False)
        if hashtag in t['text']:
            print("HASHTAG ",t['text'])
            mention_list_extraction(twitter,(t['user']['id']
                                ,t['user']['screen_name'],t['id'],t['text']),5,exemplar,True)
