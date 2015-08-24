// To serialize form into a single JSON
$.fn.serializeForm = function() {
    var o = {};
    var a = this.serializeArray();
    $.each(a, function() {
        // Take only non-empty values
        if (this.value !== "") {
            o[this.name] = this.value;
        }
    });
    return o;
};

// Resets buttons states depending on the query status
function sl_in_query(state) {
    $("#start_query").prop("disabled", state);
    $("#cancel_query").prop("disabled", !state);
}

// Cancel query request
function sl_cancel_query() {
    $.ajax({
        url: "cancel",
        type: "POST",
        data: null,
        dataType: "html",
        cache: false,
        success: function (data) {
            console.log("Cancel request passed");
        },
        error: function (xhr, status, errorThrown) {
            console.log("Error cancelling query: " + xhr.responseText);
        }
    });
}

// Next result request
function sl_next_result() {
    $.ajax({
        url: "result",
        type: "GET",
        data: null,
        dataType: "json",
        cache: false,
        success: function (data) {
            // check for eof
            if (data["eof"]) {
                alert("Query completed!");
                sl_in_query(false);
            } else {
                var result = data["result"];
                $("#records").DataTable().row.add([result["id"], result["time"],
                    result["len"]]).draw();
                sl_next_result();
            }
        },
        error: function (xhr, status, errorThrown) {
            alert("Error getting result: " + xhr.responseText);
            sl_in_query(false);
        }
    });
}

// Request waveform (clicked from the table)
function sl_get_waveform(params) {
    $.ajax({
        url: "waveform",
        type: "GET",
        data: params,
        dataType: "json",
        cache: false,
        success: function (data) {
            sl_display_waveform(data["waveform"], "id=" + params["id"] +
                " time=" + params["time"]);
        },
        error: function (xhr, status, errorThrown) {
            alert("Error getting waveform: " + xhr.responseText);
        }
    });
}

// Display waveform via Flot
function sl_display_waveform(data, plot_label) {
    var plot_data = [];
    // Add position ticks: 0,1,2,...
    for (var i = 0; i < data.length; i++) {
        plot_data.push([i, data[i]]);
    }
    $.plot("#waveform-chart", [{label: plot_label, data: plot_data}], {
        yaxis: {show: false},
        grid: {borderColor: '#ccc'}
    });
}

// $(document).ready
$(function() {
    //Prepare table
    var records_table = $("#records").DataTable();

    // Toggle neighborhood elements
    $("#neighborhood").click(function() {
        var checked = this.checked;
        $(".neighb").each(function() {
            $(this).prop("disabled", !checked);
        });
    });

    // Cancel query button
    $("#cancel_query").click(function() {
        sl_cancel_query();
    });

    // Table result click --- draw the waveform
    $("#records tbody").on("click", "tr", function() {
        var record = records_table.row(this).data();
        var waveform_params = {"signal": $("#signal").val(), "id": record[0],
                               "time": record[1], "len": record[2]};
        sl_get_waveform(waveform_params);
    });

    // Submit: create JSON and send to server
    $("form").submit(function(event) {
        var form_data_json = $("form").serializeForm();
        // Disable neighborhood querying if not checked
        if (!$("#neighborhood").prop("checked")) {
            form_data_json["mimic.neighborhood.l_size"] = 0;
            form_data_json["mimic.neighborhood.r_size"] = 0;
        }
        var form_data_json_str = JSON.stringify(form_data_json);
        // Switch buttons
        sl_in_query(true);
        // Clear the table for new results
        records_table.clear().draw();
        $.ajax({
            url: "query",
            type: "POST",
            data: form_data_json_str,
            dataType: "html",
            contentType: "application/json; charset=utf-8",
            cache: false,
            success: function (data) {
                // Immediately query for result
                sl_next_result();
            },
            error: function (xhr, status, error) {
                alert(xhr.responseText);
                sl_in_query(false);
            }
        });
        event.preventDefault();
    });
});
