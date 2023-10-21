function sendPrintJob(data, buttonElement, callback) {
    var options = {
        url: '/send-print-job',
        type: 'POST',
        success: function(response) {
            console.log("Server Response:", response);
            if (callback) callback(response, null);  // add second argument as null to represent no error
        },
        error: function(xhr, status, error) {  // handle errors from the server or network issues
            if (callback) callback(null, xhr.responseText);  // pass the error message as the second argument
        }
    };

    // If data is an instance of FormData, adjust the options for the AJAX call
    if (data instanceof FormData) {
        options.data = data;
        options.contentType = false;
        options.processData = false;
    } else {
        options.data = data;
    }

    // Make the AJAX call
    $.ajax(options);

    // Use the showMessage function to display the response
    function showMessage(element, message) {
        element.text(message).show();
        setTimeout(function() {
            element.fadeOut();
        }, 6000);  // hide after 6 seconds
    }

    // In your loop that sends print jobs, replace the alert calls with showMessage
    if (callback) {
        callback = function(response, error) {
            var messageElement = buttonElement.siblings(".responseMessage");
            if (error) {
                showMessage(messageElement, "Error: " + error);
            } else if (response && response.status === "success") {
                showMessage(messageElement, "Print job(s) sent!");
            } else {
                showMessage(messageElement, "Error: " + response.message);
            }
        }
    }
}

function updateJobsTable() {
    $.get('/get-jobs', function(data) {
        var tableBody = $('#jobsTable tbody');
        tableBody.empty();
        data.forEach(function(job) {
            var row = '<tr><td>' + job.timestamp + '</td><td>' + job.printer + '</td><td>' + job.filename + '</td><td>' + job.username + '</td><td>' + job.status + '</td></tr>';
            tableBody.append(row);
        });
    });
}

$(document).ready(function() {
    if ($('#jobsTable').length) {
        updateJobsTable();
        setInterval(updateJobsTable, 5000);
    }

    $(".printButton").click(function() {
        var buttonElement = $(this);
        var copies = $(this).siblings(".copiesInput").val(); // Get number of copies from the input field
        var data = {
            'filename': $(this).data('file'),
            'queue': $(this).data('queue'),
            'username': $(this).data('username'),
            'copies': 1 // Always sending 1 copy at a time, but we'll loop as per the number of copies
        };
    
        // Send the print job the number of times as specified by the copies input
        for (let i = 0; i < copies; i++) {
            sendPrintJob(data, buttonElement, function(response, error) {
                if (error) {
                    console.error("Error while sending print job:", error);
                } else if (response && response.status === "success") {
                    // Show alert only once after all copies are sent
                    if (i === copies - 1) {
                        showMessage($(this).siblings(".responseMessage"), "Print job(s) sent!");
                    }                    
                } else {
                    showMessage($(this).siblings(".responseMessage"), "Error: " + response.message);
                }
            });
        }
    });
    
    $("form").submit(function(e) {
        e.preventDefault();
        var formData = new FormData(this);
        sendPrintJob(formData, function(response, error) {
            if (error) {
                console.error("Error while sending print job:", error);
                $("#statusMessage").text("Print job sent!");
            } else if (response && response.status === "success") {
                $("#statusMessage").text("Job sent successfully! Job ID: " + response.data.jobID);
            } else {
                $("#statusMessage").text("Error: " + response.message);
            }
        });
    });

    document.querySelector(".menu-btn").addEventListener("click", function() {
        const navLinks = document.querySelector(".nav-links");
        if (navLinks.style.display === "none" || navLinks.style.display === "") {
            navLinks.style.display = "flex";
        } else {
            navLinks.style.display = "none";
        }
    });
    
});
