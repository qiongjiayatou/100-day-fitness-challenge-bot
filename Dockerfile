# Use an official Python runtime as the base image
FROM python:3.9

# Install tzdata
RUN apt-get update && apt-get install -y tzdata

# Set the timezone to Nicosia (Europe/Nicosia)
ENV TZ=Europe/Nicosia

# Set up the tzdata package (if needed)
RUN ln -snf /usr/share/zoneinfo/Europe/Nicosia /etc/localtime && echo "Europe/Nicosia" > /etc/timezone


# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app

# Run the bot when the container launches
CMD ["python", "main.py"]