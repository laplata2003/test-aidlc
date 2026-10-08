# User Stories — Plan and Questions

Plan summary (proposed, from the approved requirements):

- Personas: two. The application developer who calls the limiter to guard a resource, and the test author or maintainer who controls time and cleanup.
- Story format: "As a [persona], I want [goal], so that [benefit]", checked against INVEST, with Given/When/Then acceptance criteria.
- Priority: Must Have, Should Have, Could Have, Won't Have for each story.

## Question 1
How should the stories be broken down? This decides how many stories there are and how big each one is.

A. By operation: configure, check, reset, cleanup, and time control, one story each (about 6 stories)
B. By persona: a few larger stories per persona (about 3 stories)
C. By workflow: allow under the limit, block over the limit, recover after the window, and clean up idle clients (about 5 stories)
X. Other (please specify)

[Answer]: C

## Question 2
Should thread safety (FR5.5) and the periodic background cleanup (FR5.4) get their own stories, or be folded into the operation stories? Both were marked as assumptions or optional in the requirements.

A. Own stories, ranked Should Have, so they get their own acceptance criteria and tests
B. Folded into the check and cleanup stories as extra acceptance criteria
X. Other (please specify)

[Answer]: A
