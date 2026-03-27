# OpenTelemetry Tutorial
In this repo, we will provide a basic introduction to **OpenTelemetry**. OpenTelemetry, often referred to as **OTel** for short, is a standarized means of capturing **signals** from your application. We'll cover more in depth what signals means, but essentially, OTel provides a standard framework for recording a variety of different kinds of information about your running application.

> [!NOTE]
> This repo is still a work in progress. If you are looking for the code that we wrote during the part 1 stream, please see the `stream` directory. I have a "cleaner" version of the code under `src`.


## What is telemetry?
The definition of **telemetry** as Wikipedia notes is the following: *telemetry is the in situ collection of measurements or other data at remote points and their automatic transmission to receiving equipment for monitoring. The word is derived from the Greek roots tele, 'far off', and metron, 'measure'.* That's not a bad definition, but it can be a bit confusing, so let's ground this definition another.

Imagine that you have a software application running in production. It could be anything: a website, an iOS application, an API. You can probably think of many different reasons we'd want to collect information about that piece of running software in production. Maybe you want to collect extensive logs to help if anything needs debugged down the road. Maybe you want to keep track of how many times a certain API endpoint is hit. Or if you're working in the GenAI context, maybe you want to capture all the steps an agentic AI took from start to finish. All of those examples contain information you want to capture, and we refer to this specific information as telemetry.

The important thing to remember about telemetry is that generally speaking, you're collecting telemetry from some software application hosted on one server and storing the telemetry on some other form of server. (They technically can be the same server, but this would be less common.) In other words, we have to get the telemetry from Point A (your software application in production) to Point B (where you intend to land your telemetry). As you can imagine, there are a billion ways under the sun to do this.

Enter OpenTelemetry.



## Why OpenTelemetry (OTel)?
As we ended the previous section, getting the telemetry where it needs to go can be done in many, many ways. Naturally, if you don't have some form of standardization, it can be very challenging to collect your telemetry in a standardized way if everybody is sending you their telemetry in its own way.

OTel was designed to provide that level of standardization to telemetry. It is an open source framework that manifests support in many different programming languages, including Python, which we'll be working with in this tutorial.

In the next few sections, we'll dive deeper into what this standardization looks like. We'll also demonstrate this tangibly with Python code.



## What are we building?
In this repo, we'll be building an API to **fulfill pizza orders**. Naturally, this is a fun, made-up example, so the data we'll use has been totally fabricated by me. (Well, me + AI, but who's asking?) This API will simulate the flow of a pizza from start to finish, including calculating the price of a pizza and simulating the prep / bake time.

We'll be manifesting this API as a **Python-based FastAPI instance**, and we'll be serving this API out of a **Docker container**. The base code of the API is rather simple, although it may look complex because there is far more code representing the OpenTelemetry configuration than there is functional code itself! In reality, your own application will be far more complex and telemetry needs different, so don't hold the assumption that OTel code overwhelmingly bloats overall code. We're **intentionally** going a bit overboard with the OTel code for our pizza order API.