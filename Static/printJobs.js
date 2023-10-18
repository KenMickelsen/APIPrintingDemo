function sendPrintJob(data, callback) {
    var options = {
        url: '/send-print-job',
        type: 'POST',
        success: function(response) {
            console.log("Server Response:", response);
            if (callback) callback(response);
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

    $.ajax(options);
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
        var data = {
            'filename': $(this).data('file'),
            'queue': $(this).data('queue'),
            'username': $(this).data('username'),
            'copies': $(this).data('copies')
        };
        sendPrintJob(data, function(response) {
            alert(response.status === "success" ? "Job sent successfully!" : "Error: " + response.message);
        });
    });

    $("form").submit(function(e) {
        e.preventDefault();
        var formData = new FormData(this);
        sendPrintJob(formData, function(response) {
            $("#statusMessage").text(response.status === "success" ? "Job sent successfully! Job ID: " + response.data.jobID : "Error: " + response.message);
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
