"""Random greeting messages for chatrooms when no user messages exist."""

import random
from typing import List

# Collection of friendly greeting messages for sub-accounts
GREETING_MESSAGES: List[str] = [
    "Hey there! 👋 How's your day going?",
    "Hi! I'm so excited to chat with you! 😊",
    "Hello! What's on your mind today?",
    "Hey! Hope you're having an amazing day! ✨",
    "Hi there! I'd love to get to know you better 💕",
    "Hello! What brings you here today?",
    "Hey! Ready for some fun conversation? 🎉",
    "Hi! I'm here and ready to chat whenever you are!",
    "Hello beautiful! How can I brighten your day? ☀️",
    "Hey! I've been looking forward to talking with you!",
    "Hi! Tell me something interesting about yourself!",
    "Hello! What's the best part of your day so far?",
    "Hey there! I'm all ears - what would you like to talk about?",
    "Hi! Let's make this conversation memorable! 💫",
    "Hello! I hope we can have some great chats together!",
    "Hey! What's your favorite thing to do for fun?",
    "Hi! I'm curious to learn more about you!",
    "Hello! Ready to have some laughs together? 😄",
    "Hey! What's something that made you smile recently?",
    "Hi! I'm here to make your day a little brighter! 🌟",
]


def get_random_greeting() -> str:
    """
    Get a random greeting message.

    Returns:
        str: A random greeting message
    """
    return random.choice(GREETING_MESSAGES)
