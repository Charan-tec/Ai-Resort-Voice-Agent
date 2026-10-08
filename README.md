
# AI Resort Voice Agent

An AI-powered resort voice concierge that allows guests to interact naturally with a resort using voice. The system can understand guest requests, search resort knowledge, check room availability, calculate prices, create booking holds, confirm reservations, and answer resort-related questions.

---

# 🎯 Main Goal

The main goal of this project is to build a production-oriented AI Resort Voice Agent that combines:

- Voice AI
- Generative AI
- Agentic Tool Calling
- RAG
- Real-time WebSockets
- PostgreSQL
- Booking Automation
- Full-Stack Web Application

The guest can communicate naturally with the AI instead of navigating through a traditional IVR system.

Example:

Guest:
"I need a room for two people from November 21 to November 25."

The AI Agent:

1. Understands the request
2. Identifies the required dates and guests
3. Checks room availability
4. Presents available rooms
5. Calculates the selected room price
6. Creates a temporary booking hold
7. Waits for guest confirmation
8. Confirms the booking
9. Sends confirmation
10. Continues answering follow-up questions

---

# 🔊 Voice Pipeline

The voice pipeline is designed for real-time conversational interaction.

Customer
   ↓
Browser Voice / Telephony Adapter
   ↓
WebSocket Audio Stream
   ↓
Streaming Speech-to-Text
   ↓
Voice Activity / Turn Detection
   ↓
Turn Manager
   ↓
AI Agent / LLM Orchestrator
   ↓
Agentic Tools + RAG
   ↓
LLM Response
   ↓
Sentence Chunking
   ↓
Streaming Text-to-Speech
   ↓
Audio Pacing
   ↓
Customer

### Voice Processing Flow

1. Customer speaks
2. Audio is streamed to the backend
3. Speech-to-text converts audio into text
4. Turn Manager identifies the user's completed turn
5. AI Agent analyzes the request
6. Agent decides whether tools or RAG are required
7. Backend executes the required operation
8. LLM generates the response
9. Response is converted to speech
10. Audio is streamed back to the customer

### Barge-In

The system supports interruption while the AI is speaking.

AI Speaking
   ↓
Customer Starts Speaking
   ↓
Barge-In Detection
   ↓
Cancel Current LLM/TTS Work
   ↓
Flush Audio Queue
   ↓
Continue New User Turn

This allows the interaction to feel more like a natural human conversation.

### Current Demo

The public recruiter demo uses browser-based real-time voice interaction.

The architecture also contains separate telephony adapters for connecting the voice pipeline to production telephony providers.

---

# 🤖 AI Agent

The AI Agent is the main decision-making layer of the application.

It receives the user's request and determines what action is required.

The agent can:

- Understand natural language
- Maintain conversation context
- Detect booking intent
- Extract dates and guest counts
- Select rooms
- Calculate prices
- Execute booking operations
- Search resort knowledge
- Answer follow-up questions
- Maintain booking context

The LLM does not directly modify the database.

Instead, it uses controlled backend tools.

User
   ↓
AI Agent
   ↓
Decision
   ↓
Tool / RAG / Normal Response
   ↓
Result
   ↓
AI Response

---

# 🛠️ 6 Agentic Tools

The system contains six primary agentic tools.

## 1. check_availability()

Checks the database for rooms available for the requested:

- Check-in date
- Check-out date
- Number of guests
- Room requirements

Output includes available rooms and their details.

---

## 2. calculate_price()

Calculates the total booking price.

The calculation considers:

- Selected room
- Number of nights
- Room rate
- Applicable taxes / charges
- Booking context

The database remains the source of truth for room pricing.

---

## 3. create_booking()

Creates a temporary booking hold.

The booking is not immediately treated as permanently confirmed.

The system creates a temporary 15-minute courtesy hold while waiting for customer confirmation.

Flow:

Room Selected
   ↓
create_booking()
   ↓
Pending Booking
   ↓
15-Minute Hold
   ↓
Customer Confirmation

---

## 4. save_booking()

Finalizes the pending booking after customer confirmation.

Flow:

Pending Booking
   ↓
Customer Says "Confirm"
   ↓
save_booking()
   ↓
Database Transaction
   ↓
Confirmed Booking

The booking lifecycle is intentionally separated into:

Create Hold → Confirm Booking

This provides safer booking behavior.

---

## 5. send_confirmation_email()

Sends booking confirmation information to the customer.

The confirmation can include:

- Booking ID
- Guest information
- Room
- Check-in
- Check-out
- Number of guests
- Total price

---

## 6. search_resort_knowledge()

Searches the resort knowledge base for non-transactional resort information.

Examples:

- Breakfast timings
- Pool timings
- Restaurant information
- Spa information
- Resort facilities
- Activities
- Resort policies
- Guest services

---

# 🧠 RAG Architecture

The system uses Retrieval-Augmented Generation to answer resort-specific questions.

Instead of asking the LLM to generate resort information from memory, the system retrieves relevant information from the resort knowledge base.

Documents
   ↓
Document Loading
   ↓
Text Splitting
   ↓
Embeddings
   ↓
Vector Store
   ↓
Retriever
   ↓
Relevant Context
   ↓
LLM
   ↓
Grounded Answer

### RAG Components

- LangChain
- Document Loaders
- Text Splitters
- Embeddings
- Chroma Vector Database
- Retriever
- LLM

---

# 📚 Research Knowledge Base

The Research Knowledge Base contains information required by the AI Concierge to answer guest questions.

Example knowledge categories:

### Resort Information

- Resort overview
- Location
- Check-in / check-out
- General policies

### Rooms

- Room types
- Room descriptions
- Room facilities
- Capacity
- Amenities

### Dining

- Restaurants
- Breakfast
- Lunch
- Dinner
- Dining timings
- Food services

### Facilities

- Swimming pool
- Infinity pool
- Spa
- Gym
- Beach access
- Recreation areas

### Experiences

- Resort activities
- Local experiences
- Outdoor activities
- Family activities

### Guest Services

- Housekeeping
- Concierge
- Transportation
- Guest support

The knowledge base is separated from transactional booking data.

RAG is used for informational questions.

PostgreSQL is used for transactional booking information.

---

# ⚡ Structural RAG

The RAG architecture follows a structured retrieval approach.

User Question
   ↓
Query Understanding
   ↓
Retriever
   ↓
Relevant Documents
   ↓
Context Construction
   ↓
LLM
   ↓
Grounded Response

### Speculative RAG

The system also supports speculative retrieval.

During an ongoing conversation, interim speech information can be used to start retrieval before the final user turn is completed.

Interim Speech
   ↓
Potential Query
   ↓
Background Retrieval
   ↓
Cache
   ↓
Final User Question
   ↓
Reuse Retrieved Context
   ↓
LLM Response

This reduces unnecessary retrieval latency during real-time conversations.

---

# 🏨 Booking Workflow

The booking workflow is designed around safe transactional operations.

Guest Request
   ↓
Extract Dates + Guests
   ↓
Check Availability
   ↓
Show Available Rooms
   ↓
Guest Selects Room
   ↓
Calculate Price
   ↓
Create 15-Minute Hold
   ↓
Ask for Confirmation
   ↓
Guest Confirms
   ↓
Save Booking
   ↓
Booking Confirmed
   ↓
Send Confirmation Email

### Booking Lifecycle

PENDING
   ↓
CONFIRMED

If the customer does not confirm within the hold period, the pending reservation can expire.

---

# 🗄️ Database Booking Protection

PostgreSQL is used as the source of truth for reservations.

The system uses PostgreSQL `btree_gist` exclusion constraints to prevent overlapping reservations for the same room.

Conceptually:

Same Room
   +
Overlapping Dates
   ↓
Booking Conflict
   ↓
Database Prevents Overlap

This protects the system against double booking and concurrent booking requests.

---

# 🖥️ Frontend

The frontend is a premium resort dashboard built using React and Vite.

The interface is designed to look like a real customer-facing resort application rather than a technical AI demo.

### Main Sections

- Home
- Rooms & Villas
- Dining
- Experiences
- AI Concierge
- My Booking
- Logout

### AI Concierge

The AI Concierge provides:

- Voice interaction
- Text interaction
- Quick actions
- Booking assistance
- Resort information
- Booking status

### Frontend Architecture

React
   ↓
Frontend Services
   ↓
REST APIs
   ↓
FastAPI Backend

For real-time voice:

React
   ↓
WebSocket
   ↓
FastAPI
   ↓
Voice Pipeline

---

# 🔐 Security

Security is implemented across the application.

### Application Security

- Environment variables for secrets
- No API keys committed to GitHub
- Production secret validation
- CORS configuration
- Rate limiting
- Session protection

### Voice / Telephony Security

- Webhook signature verification
- HMAC-based session protection
- Secure WebSocket connections

### Database Security

- PostgreSQL transactions
- Database constraints
- Booking concurrency protection
- Controlled tool-based database access

### Secret Management

Sensitive credentials are stored in environment variables.

Examples:

- LLM API keys
- STT API keys
- TTS API keys
- Database credentials
- Telephony credentials
- Secret keys

---

# ⚙️ Backend

The backend is built using Python and FastAPI.

### Backend Responsibilities

- REST API
- WebSocket handling
- Voice processing
- AI orchestration
- Agent tool execution
- RAG retrieval
- Booking management
- PostgreSQL operations
- Session management
- Authentication / security
- Health checks
- Email processing

### Backend Flow

Frontend / Voice
      ↓
FastAPI
      ↓
Session Manager
      ↓
AI Orchestrator
      ↓
Tools / RAG
      ↓
PostgreSQL / Chroma
      ↓
Response
      ↓
Frontend / Voice

---

# 🧰 Technology Stack

## Frontend

- React
- Vite
- JavaScript

## Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic

## AI / LLM

- Google Gemini
- LangChain
- Agentic Tool Calling
- RAG

## Speech

- AssemblyAI
- ElevenLabs
- Streaming STT
- Streaming TTS

Provider abstractions are also maintained for additional STT/TTS integrations.

## Voice / Communication

- WebSockets
- Browser Voice
- Twilio adapter
- Exotel adapter

## Databases

- PostgreSQL
- Chroma

## Deployment

- GitHub
- Render
- Vercel
- Docker

---

# 🧪 Testing

The project includes testing across the complete application lifecycle.

### Backend Testing

- Unit Tests
- Integration Tests
- Tool Tests
- Database Tests
- API Tests

### AI Testing

- Agent behavior
- Tool selection
- Context retention
- RAG retrieval
- Follow-up questions

### Voice Testing

- Browser voice
- WebSocket connection
- Speech recognition
- Text-to-speech
- Barge-in
- Multi-turn conversations

### Booking Testing

- Availability
- Price calculation
- Booking hold
- Booking confirmation
- Booking expiration
- Duplicate booking protection
- PostgreSQL concurrency

### Frontend Testing

- Production build
- API integration
- WebSocket integration
- Booking UI
- AI Concierge

The complete project has been tested through automated tests and end-to-end scenarios.

---

# 📋 Project Tracker

## Phase 1 — Project Foundation

- Project structure
- FastAPI backend
- React frontend
- Environment configuration
- Git repository

Status: Completed

---

## Phase 2 — Database

- PostgreSQL setup
- SQLAlchemy models
- Alembic migrations
- Room inventory
- Booking tables
- Pricing
- Database constraints

Status: Completed

---

## Phase 3 — AI Agent

- LLM integration
- Agent orchestration
- Session management
- Context retention
- Tool calling

Status: Completed

---

## Phase 4 — Agentic Tools

- check_availability()
- calculate_price()
- create_booking()
- save_booking()
- send_confirmation_email()
- search_resort_knowledge()

Status: Completed

---

## Phase 5 — RAG

- Document ingestion
- Chunking
- Embeddings
- Chroma
- Retrieval
- Resort knowledge base
- Speculative retrieval

Status: Completed

---

## Phase 6 — Voice

- Streaming STT
- Voice session management
- WebSockets
- Streaming TTS
- Audio pacing
- Barge-in handling

Status: Completed

---

## Phase 7 — Frontend

- Resort dashboard
- Rooms
- Dining
- Experiences
- AI Concierge
- Booking UI
- Voice interface

Status: Completed

---

## Phase 8 — Security

- Secret management
- CORS
- WebSocket security
- Webhook verification
- Rate limiting
- Database protection

Status: Completed

---

## Phase 9 — Testing

- Unit tests
- Integration tests
- E2E tests
- Voice tests
- Booking tests
- RAG tests
- Frontend production build

Status: Completed

---

## Phase 10 — Deployment

- GitHub repository
- Backend deployment
- PostgreSQL deployment
- Frontend deployment
- Production REST API
- Production WebSocket
- Production health checks

Status: Completed

---

# 🚀 Deployment

The project uses a separated frontend and backend deployment architecture.

GitHub
   │
   ├──────────────► Vercel
   │                  │
   │                  ▼
   │              React Frontend
   │
   └──────────────► Render
                      │
                      ├── FastAPI Backend
                      │
                      └── PostgreSQL

### Frontend

Deployed using Vercel.

### Backend

Deployed using Render.

### Database

PostgreSQL is deployed separately and connected to the backend.

### Communication

Frontend
   ↓
HTTPS REST API
   ↓
FastAPI Backend

Frontend Voice
   ↓
Secure WebSocket
   ↓
FastAPI Voice Endpoint

---

# 🌐 Production Architecture

Customer
   ↓
React Resort Dashboard
   ↓
Vercel
   ↓
HTTPS / WebSocket
   ↓
FastAPI Backend
   ↓
AI Orchestrator
   ├── LLM
   ├── Agentic Tools
   └── RAG
        ↓
   ┌───────────────┐
   │               │
   ▼               ▼
PostgreSQL       Chroma
   │
   ▼
Booking System
   ↓
Confirmation
   ↓
Customer

---

# ⭐ Project Highlights

## 1. Real-Time Voice AI

Built a real-time voice interaction pipeline using streaming speech recognition, LLM orchestration, and streaming text-to-speech.

## 2. Agentic Architecture

The AI Agent can dynamically select backend tools based on the customer's request.

## 3. Six Production-Oriented Tools

Implemented six controlled tools for availability, pricing, booking, confirmation, email, and knowledge retrieval.

## 4. RAG Knowledge System

Implemented a resort-specific RAG pipeline using LangChain and Chroma.

## 5. Speculative Retrieval

Implemented background retrieval to reduce perceived response latency during voice conversations.

## 6. Real Booking System

The AI does not simulate bookings only.

It interacts with PostgreSQL-backed booking logic.

## 7. Double Booking Protection

PostgreSQL constraints protect the system from overlapping reservations.

## 8. Booking Hold System

Bookings are created as temporary holds before final confirmation.

## 9. Barge-In

Customers can interrupt the AI while it is speaking.

## 10. Full-Stack Application

The project contains both:

- Customer-facing React frontend
- FastAPI AI backend

## 11. Production-Oriented Security

Implemented environment-based secrets, CORS controls, session protection, webhook verification, rate limiting, and database-level protection.

## 12. Cloud Deployment

The application is deployed using:

- GitHub
- Vercel
- Render
- PostgreSQL

---

# 🎯 Final Objective

The final objective of the project is to create an AI-powered digital resort concierge that can handle a complete guest interaction from conversation to business execution.

Guest
   ↓
Voice
   ↓
AI Agent
   ↓
RAG + Agentic Tools
   ↓
Business Logic
   ↓
PostgreSQL
   ↓
Booking
   ↓
Confirmation
   ↓
Voice Response

In simple terms:

This project combines Voice AI + Generative AI + Agentic Tool Calling + RAG + PostgreSQL + Full-Stack Development to create an intelligent AI Resort Concierge.
