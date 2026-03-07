# Tribal

A basic tool for tracking expiration dates on certificates, API keys, DRIs, and renewal/generation process.

## Goal

Goal: Build a basic web application with minimal external dependencies that allows teams to define a resource that expires and/or needs to be rotated perodically. When they define the resource they need to provide data regarding the following:

* Name of resource
* DRI
* Expiration / Rotation date
* Purpose / Usage
* Generation Instructions
* Link to resource in secret manager
* Reminder Contact (Slack webhook)

The tool will send reminders 30, 14, 7, and 3 days before a change is required and stop if the resource is updated in Tribal. It should also have support for uploading a PUBLIC KEY (no private keys, no .p12, no .p7b, no .key, no PKCS#12, etc.) and extracting the expiry date automatically.

The expiry/rotation should be available in a date picker or with the choice to enter the date via a text field in MM/DD/YYYY format.

## Tech

* Python
* FastAPI
* SQLite (for now)

## Development Feedback

### Iteration 1

Feedback from the first round of testing that needs to be addressed:

* Deleting a resource should require a custom modal that requires typing in the name of the resource and warns the user that a Slack message will be sent informing the owning team that the resouce was deleted.
* On the overview tab, the calendar and upcoming events should be 50/50 in terms of width.
* The create/edit model does not have the public certificate upload option.
* The duplicate date field is not necessary, the calendar selector is sufficient.
* On the All Resources tab, I should be able to sort by name (alphabetical), DRI, Expiration, and Status
* Add an additional field to the resources: Type (API key, SSH key, certificate). This should also be an option on the All Resources tab and be a sortable column.

### Iteration 2

* Make the top bar 10% taller.
* Add the logo "tribal_logo.png" to the left of the "Tribal" text on the top bar.
* Add a button for sending a test message on the create/edit resource modal. Message contents: "This is a test message from Tribal."
* From the overview page, if you click on an upcoming event, instead of showing it below the calendar with the edit delete button, I'd prefer a model pop up over the calendar that shows the details but the fields should not allow edits unless you click on an Edit button from the modal.
* If "Cerificate" is selected from the "Type" drop down, show the certificate upload option. 

### Iteration 3

* The popover modal when viewing a resource from the Overview tab lists the "Name" field as "Other" mistakenly.
* The close button on the modal is redundant with X at the top right.
* The modal should switch the order of the "Delete" and "Edit" buttons so delete is the right-most button.
* On the "Resources" tab, there's a second "Add Resource" button. This is redundant.
* Update the text "Track expiration dates on certificates, API keys, and more." to say "Stay on top of expiration dates and rotation processes for certs, API keys, and more."
* Use the same PNG as the favicon. This might require redirecting favicon.ico to this image but if you can convert and add a smaller version of this image in .ico format, that is preferred.
* Can we add the ability to view the calendar in a full year view?
* If a HTTP link is added to the "Purpose / Usage" or "Generation / Rotation Instructions", it should be clickable.

### Iteration 4

* The "Year View" button should show the calendar filling the entire calendar-panel instead of just half.
* If "Certificate" is selected, the upload button should fall immediately above the date picker instead of at the bottom.
* Add an "About" option to the nav class with a little explainer of the tool and it's purpose. I'll fill this in more later.
* Nothing to implement here BUT can you output a plan for what it would take to make this a multi-tenant application with admins/users/teams, Entra auth, audit logs, and other common SaaS-oriented admin features. No need to make this product particularly complicated but now that we're close to having the core problem solved, it's time to consider how to turn this into a fully-fledged SaaS application.

### Iteration 5

* The Upcoming sidebar should only show events that occurr within the next 30 days.
* If a resource expires within 7 days, it should be red. If it's past due, the text should be red and the item should be highlighted in red in the UI.
* The "Year View" should maintain the same dimensions as the "Month View" with the upcoming column still present.
* Change "About" to "Docs" and leave the content as-is for now.
* Between "Docs" and "Resources" Add an additional tab called "Admin". This is where admin configuration (like around notification policies, org timezones, allow deletion, admin notifications, etc.) will be managed.
* Add unit tests to the code, verify they work, and add the tests into the CI workflow before building and publishing the latest image.

### Iteration 6

* At least try to make the application load nicely on a mobile device. 
* Today button is redundant on the calendar and should be removed as long as you keep the current day circled in blue.

### Iteration 7

* No need to run Terraform Apply as part of the build since the app will deploy when it detects a new image pushed to the DO container registry. Switch this to workflow_dispatch / on-demand.
* The Upcoming banner should include overdue items and conditionally say "[X overdue,] [N within 30 days.]" If there's nothing, it should say "Zarro items expiring." Mispelling intentional (it's a nod to Bugzilla.)
* Resources table is broken on mobile. The actions buttons are split and it breaks the table at that column.
* Before we get too far ahead, I want to have you go back through the SAAS_ROADMAP.md file and make sure we've not done anything so far that breaks that plan. Additionally, I want to encorporate roles (read-only, user, admin) to control levels of access. I also want to make notification configuration (when to notify (to drive what days), timezone config (to drive time of day), something else that's managed by admins). Finally, I think when something is deleted, it should be marked as deleted but not actually deleted from the database. We can address actually deleting things later. Additionally, I think we'll need to ensure notifications are handled and let those get handled by another process. Perhaps celery queue? This opens the door to scaling the application later. For scheduling these jobs perhaps we can use the simple scheduler library to run periodically and look for anything that needs to be acted on for notifications and then queue these up (deletions for example should be immediately scheduled for notification). On this, I think being able to schedule a report to be downloaded (recent changes and upcoming expiry) would be useful. Finally,  NOTHING TO IMPLEMENT YET JUST WANT TO KEEP ON TOP OF OUR PLAN AS THE APP CHANGES. Feel free to ask clarifying questions you have regarding this before you update the plan file.

### Iteration 8

* Put the "Today" button back that was removed previously but call it "Current Month".