# Importing flask module in the project is mandatory
# An object of Flask class is our WSGI application.
from flask import Flask
import os
 
# Flask constructor takes the name of
# current module (__name__) as argument.
app = Flask(__name__)
 
# The route() function of the Flask class is a decorator,
# which tells the application which URL should call
# the associated function.
@app.route("/")
def hello_world():
    name = os.environ.get("NAME", "World This is your first app!")
    return "Hello {}!".format(name)
 
# main driver function
if __name__ == "__main__":
 
    # run() method of Flask class runs the application
    app.run(debug=True, host="0.0.0.0", threaded=True, port=int(os.environ.get("PORT", 8080)))