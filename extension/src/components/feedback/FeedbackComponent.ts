/**
 * FeedbackComponent Component
 * User feedback collection (thumbs up/down + questionnaire)
 */

export interface FeedbackComponentProps {
  messageId: string;
  onSubmit: (messageId: string, rating: 'up' | 'down', feedback?: any) => void;
  isVisible?: boolean;
}

export function FeedbackComponent({ messageId, onSubmit, isVisible = true }: FeedbackComponentProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'feedback-capture';
  container.id = `feedbackBlock-${messageId}`;
  if (!isVisible) {
    container.style.display = 'none';
  }
  
  const rating = document.createElement('div');
  rating.className = 'feedback-rating';
  rating.id = `rating-${messageId}`;
  
  const label = document.createElement('label');
  label.textContent = 'Was this helpful?';
  
  const thumbsContainer = document.createElement('div');
  thumbsContainer.className = 'thumbs-buttons';
  
  const thumbsUp = document.createElement('button');
  thumbsUp.className = 'thumbs-btn thumbs-up';
  thumbsUp.textContent = '👍';
  thumbsUp.title = 'Helpful';
  
  const thumbsDown = document.createElement('button');
  thumbsDown.className = 'thumbs-btn thumbs-down';
  thumbsDown.textContent = '👎';
  thumbsDown.title = 'Not helpful';
  
  const questionnaire = document.createElement('div');
  questionnaire.className = 'feedback-questionnaire';
  questionnaire.id = `feedback-${messageId}`;
  
  const questionItem1 = document.createElement('div');
  questionItem1.className = 'question-item';
  const select = document.createElement('select');
  select.innerHTML = `
    <option>What could be improved?</option>
    <option>More details needed</option>
    <option>Faster response</option>
    <option>Better explanation</option>
    <option>Other</option>
  `;
  questionItem1.appendChild(select);
  
  const questionItem2 = document.createElement('div');
  questionItem2.className = 'question-item';
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Comments (optional)';
  questionItem2.appendChild(input);
  
  const submitBtn = document.createElement('button');
  submitBtn.className = 'feedback-submit';
  submitBtn.textContent = 'Submit';
  
  const toggle = document.createElement('span');
  toggle.className = 'feedback-toggle';
  toggle.textContent = 'Hide feedback';
  
  const handleRating = (ratingType: 'up' | 'down') => {
    [thumbsUp, thumbsDown].forEach(btn => btn.classList.remove('active'));
    if (ratingType === 'up') {
      thumbsUp.classList.add('active');
    } else {
      thumbsDown.classList.add('active');
    }
    questionnaire.classList.add('show');
  };
  
  thumbsUp.addEventListener('click', () => handleRating('up'));
  thumbsDown.addEventListener('click', () => handleRating('down'));
  
  submitBtn.addEventListener('click', () => {
    const ratingType = thumbsUp.classList.contains('active') ? 'up' : 'down';
    const feedback = {
      rating: ratingType,
      improvement: select.value,
      comments: input.value
    };
    onSubmit(messageId, ratingType, feedback);
    
    // Show submitted message
    rating.innerHTML = '<div class="feedback-submitted">✓ Feedback submitted. Thank you!</div>';
    
    // Auto-collapse after 2 seconds
    setTimeout(() => {
      container.style.display = 'none';
    }, 2000);
  });
  
  toggle.addEventListener('click', () => {
    if (container.style.display === 'none') {
      container.style.display = 'block';
      toggle.textContent = 'Hide feedback';
    } else {
      container.style.display = 'none';
      toggle.textContent = 'Show feedback';
    }
  });
  
  questionnaire.appendChild(questionItem1);
  questionnaire.appendChild(questionItem2);
  questionnaire.appendChild(submitBtn);
  
  thumbsContainer.appendChild(thumbsUp);
  thumbsContainer.appendChild(thumbsDown);
  
  rating.appendChild(label);
  rating.appendChild(thumbsContainer);
  rating.appendChild(questionnaire);
  rating.appendChild(toggle);
  
  container.appendChild(rating);
  
  return container;
}
