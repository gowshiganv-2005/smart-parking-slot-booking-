const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
require('dotenv').config();

const app = express();
const PORT = process.env.FEEDBACK_PORT || 5001;

// Middleware
app.use(cors());
app.use(bodyParser.json());

// MongoDB Connection
// Change the URI in your .env file
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/smart_parking';

mongoose.connect(MONGODB_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true
}).then(() => {
    console.log('Connected to MongoDB Successfully');
}).catch((err) => {
    console.error('MongoDB Connection Error:', err);
});

// Feedback Schema
const feedbackSchema = new mongoose.Schema({
    name: { type: String, required: true },
    email: { type: String, required: true },
    rating: { type: Number, required: true, min: 1, max: 5 },
    feedback: { type: String, required: true },
    createdAt: { type: Date, default: Date.now }
});

const Feedback = mongoose.model('Feedback', feedbackSchema);

// API Endpoint: POST /api/feedback
app.post('/api/feedback', async (req, res) => {
    try {
        const { name, email, rating, feedback } = req.body;

        // Validation
        if (!name || !email || !rating || !feedback) {
            return res.status(400).json({ 
                success: false, 
                message: 'All fields (name, email, rating, feedback) are required.' 
            });
        }

        if (rating < 1 || rating > 5) {
            return res.status(400).json({ 
                success: false, 
                message: 'Rating must be between 1 and 5.' 
            });
        }

        // Create and Save Feedback
        const newFeedback = new Feedback({
            name,
            email,
            rating,
            feedback
        });

        await newFeedback.save();

        res.status(201).json({ 
            success: true, 
            message: 'Feedback submitted successfully' 
        });

    } catch (error) {
        console.error('Error saving feedback:', error);
        res.status(500).json({ 
            success: false, 
            message: 'Internal server error while saving feedback.' 
        });
    }
});

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'Feedback Service is running' });
});

app.listen(PORT, () => {
    console.log(`Feedback API Server running on port ${PORT}`);
});
