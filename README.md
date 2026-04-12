![](assets/otel-github-banner.png)
# OpenTelemetry Tutorial
In this repo, we will provide a basic introduction to **OpenTelemetry**. OpenTelemetry, often referred to as **OTel** for short, is a standarized means of capturing **signals** from your application. We'll cover more in depth what signals means, but essentially, OTel provides a standard framework for recording a variety of different kinds of information about your running application.



## Accompanying Livestreams
To support this repo, I did a two-part set of livecoding streams. Here are the links to each of those:

- [Part 1 Stream](https://www.youtube.com/live/lFdylLaIEsE?si=8ApArzuyYtsvQ0o1): This stream covers an introduction to OpenTelemetry and instruments a fake pizza order taking API written in Python.
- [Part 2 Stream](https://www.youtube.com/live/jZ3low6Sc1Y?si=qkeszC3_Np3SpzNk): This stream takes things a step further by talking about how our telemetry gets from point A (our Python API) to point B (a backend to store / make sense of our telemetry). We specifically demonstrate how to send this telemetry to the open source software SigNoz.


## What is telemetry?
The definition of **telemetry** as Wikipedia notes is the following: *telemetry is the in situ collection of measurements or other data at remote points and their automatic transmission to receiving equipment for monitoring. The word is derived from the Greek roots tele, 'far off', and metron, 'measure'.* That's not a bad definition, but it can be a bit confusing, so let's ground this definition another.

Imagine that you have a software application running in production. It could be anything: a website, an iOS application, an API. You can probably think of many different reasons we'd want to collect information about that piece of running software in production. Maybe you want to collect extensive logs to help if anything needs debugged down the road. Maybe you want to keep track of how many times a certain API endpoint is hit. Or if you're working in the GenAI context, maybe you want to capture all the steps an agentic AI took from start to finish. All of those examples contain information you want to capture, and we refer to this specific information as telemetry.

The important thing to remember about telemetry is that generally speaking, you're collecting telemetry from some software application hosted on one server and storing the telemetry on some other form of server. (They technically can be the same server, but this would be less common.) In other words, we have to get the telemetry from Point A (your software application in production) to Point B (where you intend to land your telemetry). As you can imagine, there are a billion ways under the sun to do this.

Enter OpenTelemetry.



## Why OpenTelemetry (OTel)?
As we ended the previous section, getting the telemetry where it needs to go can be done in many, many ways. Naturally, if you don't have some form of standardization, it can be very challenging to collect your telemetry in a standardized way if everybody is sending you their telemetry in its own way.

OTel was designed to provide that level of standardization to telemetry. It is an open source framework that manifests support in many different programming languages, including Python, which we'll be working with in this tutorial.

In the next few sections, we'll dive deeper into what this standardization looks like. We'll also demonstrate this tangibly with Python code. Speaking of applying these concepts to something like our Python script, we refer to that as the process of **instrumenting** the code.



## What are we building?
In this repo, we'll be building an API to **fulfill pizza orders**. Naturally, this is a fun, made-up example, so the data we'll use has been totally fabricated by me. (Well, me + AI, but who's asking?) This API will simulate the flow of a pizza from start to finish, including calculating the price of a pizza and simulating the prep / bake time.

We'll be manifesting this API as a **Python-based FastAPI instance**. The base code of the API is rather simple, although it may look complex because there is far more code representing the OpenTelemetry configuration than there is functional code itself! In reality, your own application will be far more complex and telemetry needs different, so don't hold the assumption that OTel code overwhelmingly bloats overall code. We're *intentionally* going a bit overboard with the OTel code for our pizza order API.



## OTel Signals
During our discussion on what telemetry is, we generally defined telemetry as the information you want to get from your software application. That data is collectively referred to as telemetry, and OTel breaks these down further into what are referred to as **signals**. As the name implies, each signal has a distinct purpose in what it is trying to signal to the person about the running application. Recall all the various ways in which we might be interested in collecting this information from the "What is telemetry?" section. OTel generally categorizes these examples into three different kinds of signals:

- **Traces**: Traces are an intentional structured flow of a story you're trying to tell, with each building block of the story represented by a **span**. When we think about agentic AI, a trace would tell the story of what happened from the point when the agent was first given its task and all the sequential steps it took to getting to the end. This way if we ever wanted to analyze the performance of the agent, we can go back and look at the trace (along with all its associated spans) and have a clear picture of what actually happened.
- **Logs**: Logs are similar to traces but are more so about capturing information about what took place in the application without a particular regard to sequential flow. Most often, logging is used to capture errors so that a developer can later go and assess those errors for debugging purposes.
- **Metrics**: Pretty straightforward, metrics are numerical values that help you gain information about how your software application is performing. This could range from things like how many HTTP calls an API received to counting the number of pizza orders fulfilled. (As we will see with our own example!)

(Note: If you look at OpenTelemetry's official documentation, it also seems to indicate a fourth signal type called **baggage**. I'm not sure if I'm reading the documentation correctly, so I could be misunderstanding here. As I understand it, baggage isn't a signal type like we think of the other signals. Rather, baggage is a key-value store that allows other parts of OTel to consistently represent telemetry in multiple contexts. It definitely sounds like it could be useful to support our other signals, but it doesn't seem to me like it's a signal in and of itself. Moreover, some might argue that in Python specifically, baggage is almost synonymous with a standard Python dictionary, so for our tutorial, we will not make use of baggage.)



## OTel from Point A to Point B
Recall back to the pure definition of what telemetry is: sending information to a *remote* location. In the case of OTel, when we *instrument* (aka, apply what telemetry we want to capture) something like a Python script, we may be running that Python script on one server and send the telemetry along to some other remote server, usually something that has a piece of software on it designed for managing telemetry. There are many options out there, including Data Dog and DynaTrace, and for our purposes, we will be using the **open source version of SigNoz**. We'll cover how you can easily set up SigNoz in a subsection below.

When it comes to understanding how your telemetry is sent from your application, it is important to understand it in these 3 layers:

- **Instrumentation**: This is what we're applying to something like our Python API to capture the traces, logs, and metrics. We package up this instrumentation with an **exporter**, which is represented by the Python OTel SDK in our case.
- **Collector**: This is a "middleware" layer that sits between your application and the telemetry backend. Given that we are using SigNoz, SigNoz will serve as both the collector and the final backend, but OpenTelemetry natively is set up in such a way that this collector can be its own entity entirely.
- **Backend**: We can make sense of our telemetry using some sort of backend software tool. In our case, we will be using SigNoz, which per the point above, SigNoz will serve a dual purpose by being both the collector and the backend.

Something else to be aware of is that there are generally two transfer protocols that people use to send their telemetry from their application to a collector. These transfer protocols include **gRPC** and **http**. We won't cover these too in depth for our tutorial here, but please be aware that in our specific case, we will be using gRPC. There's not necessarily a right or wrong answer here on which to choose as each comes with its pros and cons. Generally speaking, the pro of using gRPC is that it is faster, but the con is that it can be harder to debug. From my understanding, it is more ideal to go with gRPC if you can.



### SigNoz Setup
In this project, we will be using the open source software **SigNoz** as the backend to store and make use of our telemetry. Using Docker, SigNoz provides a very simple manner with setting up a simple SigNoz local instance. For context, I personally will be using my own Mac mini to host the SigNoz instance, and I will run the Python API itself on my own MacBook Pro. By doing this, I can demonstrate effectively that one server (my MacBook Pro) can effectively send telemetry to another server (my Mac Mini).

1. Clone SigNoz's repo: `git clone https://github.com/SigNoz/signoz.git`
2. Change to the appropriate directory: `cd signoz/deploy/docker`
3. Run `docker compose up -d`