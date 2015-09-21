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

// searchlight object
$.searchlight = new Object();
// Current query id
$.searchlight.query_id = null;
// The BD server address
$.searchlight.BD_URL = "http://localhost:8080/bigdawg";
// Searchlight result URL (comes from request)
$.searchlight.SL_URL = null;

// generate table for the ICU stay
$.searchlight.generate_icustay = function generate_icustay(tuple) {
    var content = "<table class=\"table table-striped table-bordered\" cellspacing=\"0\" width=\"100%\">\
                       <thead>\
                          <tr>\
                              <th>Patient ID</th>\
                              <th>ICU Stay ID</th>\
                              <th>Gender</th>\
                              <th>DOB</th>\
                              <th>In-Time</th>\
                              <th>Out-Time</th>\
                          </tr>\
                       </thead>";
    content += "<tbody><tr>";
    for (var i = 0; i < 6; i++) {
        content += "<td>" + tuple[i] + "</td>";
    }
    content += "</tr></tbody></table";
    $("#icustay").empty().append(content);
};

// Resets state depending on the query status
$.searchlight.sl_in_query = function sl_in_query(state) {
    $("#start_query").prop("disabled", state);
    $("#cancel_query").prop("disabled", !state);
    // When starting a new query reset result URL and query ID
    if (state) {
        $.searchlight.SL_URL = null;
        $.searchlight.query_id = null;
    }
};

// Create JSON for a BigDawg request
$.searchlight.make_bd_request = function make_bd_request(query_str) {
    var bigdawg_query = {query: "SEARCHLIGHT(" + query_str + ")"};
    return JSON.stringify(bigdawg_query);
};

// Creates a relay BigDawg request
$.searchlight.make_relay_bd_request = function make_relay_bd_request(
        query_str, relay_rel_url) {
    var relay_query_str = JSON.stringify({
        query: query_str,
        query_id: $.searchlight.query_id,
        "RelayURL": $.searchlight.SL_URL + "/" + relay_rel_url
    });
    return relay_query_str;
};

// Cancel query request
$.searchlight.sl_cancel_query = function sl_cancel_query() {
    $.ajax({
        url: $.searchlight.BD_URL + "/from",
        type: "POST",
        data: $.searchlight.make_relay_bd_request(null, "cancel"),
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        cache: false,
        success: function (data) {
            console.log("Cancel request passed");
        },
        error: function (xhr, status, errorThrown) {
            console.log("Error cancelling query: " + xhr.responseText);
        }
    });
};

// Next result request
$.searchlight.sl_next_result = function sl_next_result() {
    $.ajax({
        url: $.searchlight.BD_URL + "/from",
        type: "POST",
        data: $.searchlight.make_relay_bd_request(null, "result"),
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        cache: false,
        success: function (data) {
            // check for eof
            if (data["eof"]) {
                alert("Query completed!");
                $.searchlight.sl_in_query(false);
            } else {
                var result = data["result"];
                $("#records").DataTable().row.add([result["sid"], result["id"], result["pretty_time"], result["time"],
                    result["len"]]).draw();
                sl_next_result();
            }
        },
        error: function (xhr, status, errorThrown) {
            alert("Error getting result: " + xhr.responseText);
            $.searchlight.sl_in_query(false);
        }
    });
};

// Request waveform (clicked from the table)
$.searchlight.sl_get_waveform = function sl_get_waveform(params) {
    $.ajax({
        url: $.searchlight.BD_URL + "/from",
        type: "POST",
        data: $.searchlight.make_relay_bd_request(params, "waveform"),
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        cache: false,
        success: function (data) {
            $.searchlight.sl_display_waveform(data["waveform"],
                "id=" + params["id"] + " time=" + params["time"]);
        },
        error: function (xhr, status, errorThrown) {
            alert("Error getting waveform: " + xhr.responseText);
        }
    });
};

$.searchlight.get_icustay = function get_icustay(patient_id) {
    // prepare query
    query_str = "SELECT e.subject_id, e.icustay_id, gender, dob, intime, outtime, height, weight_first\
        FROM mimic2v26.icustayevents AS e, mimic2v26.icustay_detail AS d WHERE e.subject_id=" + patient_id +
        " AND d.icustay_id = e.icustay_id LIMIT 1";
    var bigdawg_query = {query: "RELATION(" + query_str + ")"};
    bigdawg_query = JSON.stringify(bigdawg_query);
    // then query
    $.ajax({
        url: $.searchlight.BD_URL + "/query",
        type: "POST",
        data: bigdawg_query,
        dataType: "json",
        contentType: "application/json; charset=utf-8",
        cache: false,
        success: function (data) {
            // retrieve the tuple and put into table
            icu_tuple = data["tuples"][0];
            $.searchlight.generate_icustay(icu_tuple);
        },
        error: function (xhr, status, error) {
            alert("Error getting data about ICU stay: ", xhr.responseText);
        }
    });
};

// Display waveform via Flot
$.searchlight.sl_display_waveform = function sl_display_waveform(
        data, plot_label) {
    var plot_data = [];
    // Add position ticks: 0,1,2,...
    for (var i = 0; i < data.length; i++) {
        plot_data.push([i, data[i]]);
    }
    $.plot("#waveform-chart", [{label: plot_label, data: plot_data}], {
        yaxis: {show: false},
        grid: {borderColor: '#ccc'}
    });
};

// $(document).ready
$(function() {
    // Prepare table (hide tick and record columns, which are used only for waveform retrieval)
    var records_table = $("#records").DataTable({
        "columnDefs": [
            {
                "targets": [4],
                "render": function(data, type, row) {
                    return data / 125; // Convert from ticks to seconds
                }
            },
            {
                "targets": [1],
                "visible": false,
                "searchable": false
            },
            {
                "targets": [3],
                "visible": false,
                "searchable": false
            }
        ]
    });

    // Toggle neighborhood elements
    $("#neighborhood").click(function() {
        var checked = this.checked;
        $(".neighb").each(function() {
            $(this).prop("disabled", !checked);
        });
    });

    // Cancel query button
    $("#cancel_query").click(function() {
        $.searchlight.sl_cancel_query();
    });

    // Table result click --- draw the waveform
    $("#records tbody").on("click", "tr", function() {
        var record = records_table.row(this).data();
        var waveform_params = {"signal": $("#signal").val(), "id": record[1],
                               "time": record[3], "len": record[4]};
        $.searchlight.sl_get_waveform(waveform_params);
        $.searchlight.get_icustay(record[0]);
    });

    // Submit: create JSON and send to server
    $("form").submit(function(event) {
        var form_data_json = $("form").serializeForm();
        // Disable neighborhood querying if not checked
        if (!$("#neighborhood").prop("checked")) {
            form_data_json["mimic.neighborhood.l_size"] = 0;
            form_data_json["mimic.neighborhood.r_size"] = 0;
        }
        var form_data_json_str = JSON.stringify({query: form_data_json});
        // Switch buttons
        $.searchlight.sl_in_query(true);
        // Clear the table for new results
        records_table.clear().draw();
        $.ajax({
            url: $.searchlight.BD_URL + "/query",
            type: "POST",
            data: $.searchlight.make_bd_request(form_data_json_str),
            dataType: "json",
            contentType: "application/json; charset=utf-8",
            cache: false,
            success: function (data) {
                // take the "tuples" field
                //data = JSON.parse(data["tuples"]);
                // Immediately query for result
                $.searchlight.query_id = data["query_id"];
                $.searchlight.SL_URL = data["result_url"];
                if (!$.searchlight.query_id || !$.searchlight.SL_URL) {
                    alert("Wrong response from the server!");
                    $.searchlight.sl_in_query(false);
                } else {
                    $.searchlight.sl_next_result();
                }
            },
            error: function (xhr, status, error) {
                alert(xhr.responseText);
                $.searchlight.sl_in_query(false);
            }
        });
        event.preventDefault();
    });
});
