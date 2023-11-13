import tweepy

# Twitter API credentials
consumer_key = 'YOUR_CONSUMER_KEY'
consumer_secret = 'YOUR_CONSUMER_SECRET'
access_token = 'YOUR_ACCESS_TOKEN'
access_token_secret = 'YOUR_ACCESS_TOKEN_SECRET'

# Set up Tweepy authentication
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Function to post a tweet
def post_tweet(tweet_text):
    try:
        api.update_status(status=tweet_text)
        print("Tweet posted successfully.")
    except tweepy.TweepError as e:
        print(f"Error posting tweet: {e}")

# Example usage
tweet_content = "Hello, this is a sample tweet from my social media tool!"
post_tweet(tweet_content)
